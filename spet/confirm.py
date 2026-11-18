"""Confirmation: retest a few screen candidates, chosen by a fixed rule, on fresh questions.

The discovery stage (spet/discovery.py) is a screen: it tests every proposed statement and corrects within two
large families. Its p-values are valid, but with ~100 hypotheses and nothing past the correction, the honest next
step is a confirmation:

1. Choose candidates from the finished screen by a rule fixed in code (``SelectionRule``), never by hand.
2. Answer fresh questions that the screen never used: for each part with an intended candidate, questions that
   target that part; for discovered candidates, general questions that target no part. Only ``full`` and the
   candidate parts' ``without_k`` are answered, with a seed that differs from the run's.
3. Judge each candidate's statement text verbatim with the same blinded judge prompt, re-judge a stratified
   sample with the equivalent second prompt, and leave out recited prompts, all as in discovery.
4. Test with the same two-sided by-question sign-flip test, and correct with Benjamini-Hochberg at the run's alpha
   within the confirmation set, intended and discovered as separate families. m is the number of candidates in
   the family, fixed by the rule: a candidate that turns out untested stays in with p = 1.
5. A candidate is confirmed if q < alpha, no blocking flag is set, and its difference has the screen's sign.

Only the confirmation supports a claim. See docs/discovery.md, "Confirmation".
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from . import attribution, prompts, schedule
from .bundle import (SCHEMA_VERSION, Candidate, ConfirmQuery, ConfirmReading, ConfirmRule, Confirmation, PairExample,
                     Response, RunBundle, Statement)
from .discovery import BLOCKING, FAMILIES, DiscoveryOptions, _Calls, _kappa, _LETTER, echo_share, judge_flags

CONFIRMED_IF = ("two-sided by-question sign-flip p, Benjamini-Hochberg q < alpha within the candidate's family "
                "(m = the family's candidates, fixed by the rule; an untested candidate counts with p = 1), no "
                "blocking flag (" + ", ".join(sorted(BLOCKING)) + "), and a difference with the same sign as in the "
                "screen; a significant difference with the opposite sign is not confirmed and gets the flag `reversed`")


@dataclass(frozen=True)
class SelectionRule:
    """Which screen statements are retested. Fixed before any confirmation answer exists; stored in the bundle."""
    intended_p_below: float = 0.1
    discovered_p_below: float = 0.01
    require_tested: bool = True
    excluded_flags: tuple[str, ...] = ("judge_unreliable", "rejudge_one_class", "ceiling", "never_seen", "few_pairs",
                                       "too_few_questions")

    def picks(self, st: Statement) -> bool:
        limit = self.intended_p_below if st.source == "intended" else self.discovered_p_below
        return (st.p < limit and (st.tested or not self.require_tested)
                and not set(self.excluded_flags) & set(st.flags))

    def record(self) -> ConfirmRule:
        return ConfirmRule(intended_p_below=self.intended_p_below, discovered_p_below=self.discovered_p_below,
                           require_tested=self.require_tested, excluded_flags=list(self.excluded_flags),
                           confirmed_if=CONFIRMED_IF)


RULE = SelectionRule()


def select(b: RunBundle, rule: SelectionRule = RULE) -> list[Statement]:
    """The screen statements the rule picks, in the screen's order."""
    if not b.discovery:
        raise ValueError("the bundle has no discovery block to confirm")
    return [st for st in b.discovery.statements if rule.picks(st)]


# ---- the spec: fresh questions -----------------------------------------------------------------------

@dataclass
class ConfirmSpec:
    id: str
    queries: list[str]
    targets: list[list[int]]     # [] = general
    seed: int
    n_per_query: int = 6         # samples per targeted question
    n_per_query_general: int = 2
    provider: dict = field(default_factory=lambda: {"kind": "stub"})
    sha256: str = ""
    file: str = ""


_QSTOP = {"the", "a", "an", "of", "to", "and", "or", "is", "are", "it", "in", "on", "for", "with", "that", "this",
          "me", "my", "you", "your", "i", "can", "could", "would", "please", "what", "how", "do", "does", "be", "at",
          "about", "from", "by", "as", "if", "so", "there", "any", "some", "into", "us", "we", "our",
          "what's", "it's", "i'm"}
_URL_PREFIX = re.compile(r"https?://(?:www\.)?")


def _qtokens(s: str) -> set[str]:
    s = _URL_PREFIX.sub(" ", s.lower().replace("\u2019", "'"))
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9']+", s) if w not in _QSTOP}


def overlap(a: str, b: str) -> float:
    """Jaccard overlap of content words: a backstop against repeated or closely paraphrased questions."""
    ta, tb = _qtokens(a), _qtokens(b)
    if not ta or not tb:
        return float(a.strip().lower() == b.strip().lower())
    return len(ta & tb) / len(ta | tb)


MAX_OVERLAP = 0.5


def load_spec(path: str | Path, b: RunBundle) -> ConfirmSpec:
    from .cli import _parse_queries

    path = Path(path)
    data = path.read_bytes()
    raw = yaml.safe_load(data)
    labels = [s.label for s in b.sections]
    try:
        texts, targets = _parse_queries(raw.get("queries") or [], labels)
    except ValueError as e:
        raise ValueError(f"{path.name}: {e}")
    if "temperature" in raw and float(raw["temperature"]) != b.meta.temperature:
        raise ValueError("the confirmation samples at the run's temperature; drop `temperature` or match it")
    return ConfirmSpec(id=raw.get("id", path.stem), queries=texts, targets=targets or [[] for _ in texts],
                       seed=int(raw["seed"]), n_per_query=int(raw.get("n_per_query", 6)),
                       n_per_query_general=int(raw.get("n_per_query_general", 2)),
                       provider=raw.get("provider", {"kind": "stub"}), sha256=hashlib.sha256(data).hexdigest(),
                       file=path.name)


def check_spec(spec: ConfirmSpec, b: RunBundle, cands: list[Statement]) -> list[float]:
    """Refuse a spec that does not fit the candidates or repeats the screen. Returns each question's overlap with
    the screen's questions."""
    if spec.seed == b.meta.seed:
        raise ValueError(f"the confirmation needs a seed other than the run's ({b.meta.seed})")
    if spec.n_per_query < 1 or spec.n_per_query_general < 1:
        raise ValueError("sample counts must be at least 1")
    want = {st.section for st in cands if st.source == "intended"}
    if any(len(t) > 1 for t in spec.targets):
        raise ValueError("a confirmation question targets at most one part")
    have = {t[0] for t in spec.targets if t}
    if have != want:
        names = lambda ks: ", ".join(b.sections[k].label for k in sorted(ks)) or "none"  # noqa: E731
        raise ValueError(f"targeted questions must cover exactly the parts with an intended candidate "
                         f"({names(want)}); the spec targets {names(have)}")
    n_general = sum(not t for t in spec.targets)
    if any(st.source == "discovered" for st in cands) != bool(n_general):
        raise ValueError("general questions (targets: []) are needed exactly when a discovered statement is a candidate")
    norm = lambda s: " ".join(s.lower().split())  # noqa: E731
    seen: dict[str, int] = {}
    for i, q in enumerate(spec.queries):
        if norm(q) in seen:
            raise ValueError(f"question {i + 1} repeats question {seen[norm(q)] + 1} of the spec")
        seen[norm(q)] = i
        for j in range(i):
            if overlap(q, spec.queries[j]) >= MAX_OVERLAP:
                raise ValueError(f"question {i + 1} nearly repeats question {j + 1} of the spec: {q!r}")
    out = []
    screen = b.meta.queries
    for i, q in enumerate(spec.queries):
        best, at = max(((overlap(q, s), j) for j, s in enumerate(screen)), default=(0.0, -1))
        if norm(q) in {norm(s) for s in screen} or best >= MAX_OVERLAP:
            raise ValueError(f"question {i + 1} repeats or nearly repeats screen question {at + 1}: {q!r} / {screen[at]!r}")
        out.append(round(best, 3))
    return out


def check_provider(cfg: dict, b: RunBundle) -> None:
    """The answers must come from the run's model with the run's generation settings."""
    kind = cfg.get("kind", "stub")
    if (kind == "stub") != (b.meta.provider == "stub"):
        raise ValueError(f"provider kind {kind!r} does not match the run's provider {b.meta.provider!r}")
    if kind == "stub":
        return
    s = b.meta.settings
    from .providers import _host
    got = {"model": cfg.get("model"), "endpoint_host": _host(cfg.get("base_url", "")),
           "max_tokens": int(cfg.get("max_tokens", 1500)),
           "reasoning_effort": (cfg.get("extra") or {}).get("reasoning_effort")}
    want = {"model": b.meta.model, "endpoint_host": s.get("endpoint_host"), "max_tokens": s.get("max_tokens"),
            "reasoning_effort": s.get("reasoning_effort")}
    bad = {k: (got[k], want[k]) for k in got if got[k] != want[k]}
    if bad:
        raise ValueError("the provider block differs from the run: " + "; ".join(f"{k} {g!r} vs {w!r}" for k, (g, w) in bad.items()))


def check_judge(judge, b: RunBundle) -> dict:
    """The judge must be the screen's: same model, host, max_tokens, reasoning effort and judge prompts. Settings the
    screen did not record (None) are not compared. Returns what was checked."""
    s, js = b.meta.settings, getattr(judge, "settings", {}) or {}
    got = {"judge_model": getattr(judge, "model", None), "judge_endpoint_host": js.get("endpoint_host"),
           "judge_max_tokens": js.get("max_tokens"), "judge_reasoning_effort": js.get("reasoning_effort"),
           "discovery_prompts_version": prompts.version()}
    bad = {k: (got[k], s.get(k)) for k in got if s.get(k) is not None and got[k] != s.get(k)}
    if bad:
        raise ValueError("the judge differs from the screen's: " + "; ".join(f"{k} {g!r} vs {w!r}" for k, (g, w) in bad.items()))
    return got


# ---- jobs and plan -------------------------------------------------------------------------------------

def question_sets(spec: ConfirmSpec, cands: list[Statement]) -> dict[str, list[int]]:
    """Confirmation questions each candidate is tested on."""
    general = [q for q, t in enumerate(spec.targets) if not t]
    return {st.id: ([q for q, t in enumerate(spec.targets) if t == [st.section]] if st.source == "intended" else
                    [q for q in general if st.section not in spec.targets[q]]) for st in cands}


def build_jobs(spec: ConfirmSpec, b: RunBundle, cands: list[Statement]) -> list[schedule.Job]:
    """``full`` and the candidate parts' ``without_k`` only. Targeted questions get n_per_query samples, general
    ones n_per_query_general. Each (question, sample) has one seed, shared by its configs, from the confirmation
    seed. Nothing but the question goes in the user message."""
    qsets = question_sets(spec, cands)
    sections = [s.text for s in b.sections]
    need: dict[int, set[int | None]] = {}
    for st in cands:
        for q in qsets[st.id]:
            need.setdefault(q, {None}).add(st.section)
    jobs = []
    for removed in [None] + sorted({st.section for st in cands}):
        cfg = "full" if removed is None else f"without_{removed}"
        system = schedule.join_sections([t for i, t in enumerate(sections) if i != removed])
        for q in sorted(need):
            if removed not in need[q]:
                continue
            n = spec.n_per_query if spec.targets[q] else spec.n_per_query_general
            jobs += [schedule.Job(cfg, removed, q, s, system, spec.queries[q], schedule.cell_seed(spec.seed, q, s))
                     for s in range(n)]
    return jobs


def plan(spec: ConfirmSpec, b: RunBundle, cands: list[Statement], opts: DiscoveryOptions | None = None) -> dict:
    """Answers and upper bounds on judge calls, before any call."""
    opts = opts or DiscoveryOptions()
    qsets = question_sets(spec, cands)
    n = lambda q: spec.n_per_query if spec.targets[q] else spec.n_per_query_general  # noqa: E731
    judge = sum(2 * n(q) for st in cands for q in qsets[st.id])
    return dict(answers=len(build_jobs(spec, b, cands)), judge=judge,
                rejudge=2 * opts.rejudge_per_class * len(cands), candidates=len(cands))


# ---- the confirmation itself ---------------------------------------------------------------------------

async def answer(jobs: list[schedule.Job], provider, temperature: float, progress=None) -> list:
    done = 0

    async def one(j):
        nonlocal done
        t = await provider.complete(j.system, j.user, temperature=temperature, seed=j.seed)
        done += 1
        if progress:
            progress(done, len(jobs))
        return t

    return list(await asyncio.gather(*(one(j) for j in jobs)))


async def confirm(b: RunBundle, spec: ConfirmSpec, provider, judge, *, rule: SelectionRule = RULE,
                  opts: DiscoveryOptions | None = None, progress=None, judge_progress=None) -> RunBundle:
    """Return a copy of ``b`` with a ``confirmation`` block: fresh answers, judgments and the confirmation test."""
    opts = opts or DiscoveryOptions()
    cands = select(b, rule)
    overlaps = check_spec(spec, b, cands)
    alpha = b.discovery.alpha
    jobs = build_jobs(spec, b, cands)
    texts = await answer(jobs, provider, b.meta.temperature, progress)

    responses, ans, cut = [], {}, 0
    for j, t in zip(jobs, texts):
        fr = getattr(t, "finish_reason", None)
        responses.append(Response(config=j.config, query_idx=j.query_idx, sample_idx=j.sample_idx, text=str(t),
                                  finish_reason=fr))
        if fr == "length" or not str(t).strip():  # same exclusion as the run
            cut += 1
            continue
        ans[(j.config, j.query_idx, j.sample_idx)] = str(t)
    systems = {j.config: j.system for j in jobs}
    echo = {k for k, t in ans.items() if echo_share(t, systems[k[0]], opts.echo_ngram) >= opts.echo_share}

    qsets = question_sets(spec, cands)
    call = _Calls(judge, judge_progress)
    queries = spec.queries
    work = []
    for st in cands:
        wo = f"without_{st.section}"
        every = sorted((q, s) for (c, q, s) in ans if c == "full" and q in qsets[st.id] and (wo, q, s) in ans)
        cells = [(q, s) for q, s in every if ("full", q, s) not in echo and (wo, q, s) not in echo]
        work.append(dict(st=st, wo=wo, cells=cells, n_echo=len(every) - len(cells)))

    def judge_one(i, cfg, q, s, alt=False):
        text, stmt = ans[(cfg, q, s)][:opts.judge_chars], work[i]["st"].text  # the statement text, verbatim
        if alt:
            return call("rejudge", prompts.JUDGE_ALT_SYSTEM, prompts.judge_alt_user(stmt, queries[q], text))
        return call("judge", prompts.JUDGE_SYSTEM, prompts.judge_user(stmt, queries[q], text))

    jobs_j = [(i, cfg, q, s) for i, w in enumerate(work) for q, s in w["cells"] for cfg in ("full", w["wo"])]
    call.expect(len(jobs_j))
    raw = await asyncio.gather(*(judge_one(*j) for j in jobs_j))
    verdict = {j: prompts.parse_verdict(r) for j, r in zip(jobs_j, raw)}

    rj_jobs = []
    for i, w in enumerate(work):
        mine = [j for j in jobs_j if j[0] == i]
        yes = [j for j in mine if verdict[j] == "yes"]
        no = [j for j in mine if verdict[j] == "no"]
        r = random.Random(f"spet-confirm-rejudge:{spec.seed}:{w['st'].id}")
        rj_jobs += r.sample(yes, min(len(yes), opts.rejudge_per_class)) + r.sample(no, min(len(no), opts.rejudge_per_class))
    call.expect(len(rj_jobs))
    rj_raw = await asyncio.gather(*(judge_one(*j, alt=True) for j in rj_jobs))
    rejudge: dict[int, list] = {}
    rj_store: dict[int, list] = {}
    for j, r in zip(rj_jobs, rj_raw):
        v2 = prompts.parse_verdict(r)
        rejudge.setdefault(j[0], []).append((verdict[j] == "yes", v2 == "yes") if v2 in ("yes", "no") else None)
        rj_store.setdefault(j[0], []).append((j[2], j[3], "w" if j[1] == "full" else "o", _LETTER[v2]))

    # ---- statistics: the screen's test, on the fresh answers ----------------------------------------
    nrng = np.random.default_rng(spec.seed + 7)
    results, n_unp = [], 0
    for i, w in enumerate(work):
        st, wo, cells = w["st"], w["wo"], w["cells"]
        f, a, groups, used = [], [], [], []
        unp = na = 0
        for q, s in cells:
            v1, v0 = verdict[(i, "full", q, s)], verdict[(i, wo, q, s)]
            unp += (v1 is None) + (v0 is None)
            na += (v1 == "na") + (v0 == "na")
            if v1 in ("yes", "no") and v0 in ("yes", "no"):
                f.append(float(v1 == "yes")); a.append(float(v0 == "yes")); groups.append(q); used.append((q, s))
        n_unp += unp
        ex_w = np.array([float(verdict[(i, "full", q, s)] not in ("yes", "no")) for q, s in cells])
        ex_o = np.array([float(verdict[(i, wo, q, s)] not in ("yes", "no")) for q, s in cells])
        asym = len(ex_w) > 0 and attribution.sign_flip_p(ex_w - ex_o, nrng) < 0.05
        f_, a_, g_ = np.array(f), np.array(a), np.array(groups)
        stats = attribution.paired_stats(f_, a_, g_, nrng, cluster=True)
        full_ci = attribution.cluster_bootstrap_ci(f_, g_, nrng) if len(f) else None
        pairs = [x for x in rejudge.get(i, []) if x is not None]
        agreement = sum(x == y for x, y in pairs) / len(pairs) if pairs else None
        kappa = _kappa([x for x, _ in pairs], [y for _, y in pairs])
        flags = judge_flags(stats, pairs, agreement, kappa, len(cells), unp, asym, opts)
        sign = 1 if st.delta >= 0 else -1  # the screen's direction
        diff = [(q, s, bool(x)) for (q, s), x, y in zip(used, f, a) if x != y]
        lead = [c for c in diff if c[2] == (sign > 0)] + [c for c in diff if c[2] != (sign > 0)]
        examples = [PairExample(query_idx=q, sample_idx=s, without_config=wo, with_yes=wy) for q, s, wy in lead[:opts.n_examples]]
        judged = [(q, s, _LETTER[verdict[(i, "full", q, s)]] + _LETTER[verdict[(i, wo, q, s)]]) for q, s in cells]
        results.append(dict(stats=stats, full_ci=full_ci, unp=unp, na=na, flags=flags, examples=examples,
                            judged=judged, agreement=agreement, kappa=kappa, n_rj=len(pairs), sign=sign,
                            exw=int(ex_w.sum()), exwo=int(ex_o.sum()), used_q=sorted({q for q, _ in used})))

    # BH within each family; m is every candidate of the family (fixed by the rule), untested ones with p = 1
    qmap, fam_n = {}, {}
    for fam in FAMILIES:
        members = [i for i, w in enumerate(work) if w["st"].source == fam]
        if not members:
            continue
        fam_n[fam] = len(members)
        ps = [results[i]["stats"]["p"] if results[i]["stats"]["tested"] else 1.0 for i in members]
        qmap.update(zip(members, attribution.benjamini_hochberg(ps)))
        for i in members:
            if attribution.cluster_p_floor(len(results[i]["used_q"])) > alpha / len(members):
                results[i]["flags"].append("too_few_questions")

    candidates = []
    for i, (w, r) in enumerate(zip(work, results)):
        st, s = w["st"], r["stats"]
        q = qmap[i]
        sig = q < alpha and not (BLOCKING & set(r["flags"]))
        same = s["delta"] * r["sign"] > 0
        if sig and not same:
            r["flags"].append("reversed")
        ok = sig and same
        candidates.append(Candidate(
            id=st.id, section=st.section, text=st.text, source=st.source,
            classification="intended" if st.source == "intended" else ("side_effect" if ok else None),
            full_rate=s["full_mean"], ablated_rate=s["ablated_mean"], full_rate_ci=r["full_ci"],
            delta=s["delta"], ci=s["ci"], ci_query=s["ci_query"], p=s["p"] if s["tested"] else 1.0, q=q,
            significant=sig, tested=s["tested"], n_pairs=s["n_pairs"], n_questions=len(r["used_q"]),
            verified_on=qsets[st.id], per_query=list(s["per_query"]), per_query_idx=list(s["per_query_idx"]),
            mde=s["mde"], n_unparseable=r["unp"], n_na=r["na"], n_excluded_with=r["exw"],
            n_excluded_without=r["exwo"], n_excluded_echo=w["n_echo"], agreement=r["agreement"], kappa=r["kappa"],
            n_rejudged=r["n_rj"], flags=r["flags"], examples=r["examples"], family=st.source,
            verdicts=r["judged"], rejudged=rj_store.get(i, []),
            screen_p=st.p, screen_q=st.q, screen_full_rate=st.full_rate, screen_ablated_rate=st.ablated_rate,
            screen_delta=st.delta, screen_n_questions=st.n_questions, confirmed=ok))

    readings = confirm_readings(b, candidates)
    warnings = []
    if cut:
        warnings.append(f"{cut} confirmation answers were cut off or empty and were left out.")
    if echo:
        warnings.append(f"{len(echo)} confirmation answers recite their own system prompt; their pairs were left out.")
    if n_unp:
        warnings.append(f"{n_unp} judge replies could not be read; they were left out with their pair.")
    if call.errors:
        warnings.append(f"{call.errors} judge calls failed and were treated as unreadable.")
    js = getattr(judge, "settings", {}) or {}
    ps = getattr(provider, "settings", {}) or {}
    settings = {
        "spec_file": spec.file, "spec_sha256": spec.sha256, "model": getattr(provider, "model", None),
        "provider": getattr(provider, "name", None), "endpoint_host": ps.get("endpoint_host"),
        "max_tokens": ps.get("max_tokens"), "reasoning_effort": ps.get("reasoning_effort"),
        "temperature": b.meta.temperature, "judge_model": getattr(judge, "model", None),
        "judge_endpoint_host": js.get("endpoint_host"), "judge_max_tokens": js.get("max_tokens"),
        "judge_reasoning_effort": js.get("reasoning_effort"), "judge_temperature": 0.0,
        "discovery_prompts_version": prompts.version(), "rejudge_per_class": opts.rejudge_per_class,
        "min_agreement": opts.min_agreement, "min_kappa": opts.min_kappa, "echo_ngram": opts.echo_ngram,
        "echo_share": opts.echo_share, "test_rng_seed": spec.seed + 7, "max_question_overlap": MAX_OVERLAP,
    }
    out = b.model_copy(deep=True)
    out.schema_version = SCHEMA_VERSION
    out.confirmation = Confirmation(
        id=spec.id, created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), seed=spec.seed, alpha=alpha,
        rule=rule.record(), n_per_query=spec.n_per_query, n_per_query_general=spec.n_per_query_general,
        queries=[ConfirmQuery(text=t, targets=tg, overlap=o) for t, tg, o in zip(spec.queries, spec.targets, overlaps)],
        configs=sorted({j.config for j in jobs}, key=lambda c: (c != "full", len(c), c)), responses=responses,
        candidates=candidates, families=fam_n, n_tests=len(candidates), readings=readings,
        prompt_echoes=sorted(echo), calls=dict(call.counts), n_unparseable=n_unp, n_errors=call.errors,
        n_cut_off=cut, warnings=warnings, settings=settings)
    return RunBundle.model_validate(out.model_dump())


SCREEN_NOTE = "From the main run, which is a screen: no claim rests on it."


def confirm_readings(b: RunBundle, cands: list[Candidate]) -> list[ConfirmReading]:
    """One reading per part. A part whose intended candidates are all confirmed reads followed; partly followed if
    some of them fail. A part with no confirmed intended candidate keeps the screen's reading (failing to confirm is
    not evidence that the instruction is not followed). A confirmed discovered candidate is a side effect of its part."""
    screen = {r.section: r for r in b.discovery.readings}
    parts = sorted({c.removed for c in b.configs if c.removed is not None})
    out = []
    for k in parts:
        mine = [c for c in cands if c.section == k]
        intended = [c for c in mine if c.source == "intended"]
        conf = [c.id for c in intended if c.confirmed]
        failed = [c.id for c in mine if not c.confirmed]
        side = [c.id for c in mine if c.source == "discovered" and c.confirmed]
        prev = screen.get(k)
        if conf:
            adh = "followed" if len(conf) == len(intended) else "partly_followed"
            note = ("Confirmed on fresh questions." if adh == "followed" else
                    "Some intended behaviour is confirmed on fresh questions; another candidate is not.")
            basis = "confirmation"
        else:
            adh = prev.adherence if prev else "not_assessed"
            basis = "screen"
            note = SCREEN_NOTE
            if intended:
                note += " Its intended candidate(s) were retested on fresh questions and not confirmed."
        if side:
            note += " Side effect confirmed on fresh questions."
        elif any(c.source == "discovered" for c in mine):
            note += " A side-effect candidate was retested and not confirmed."
        out.append(ConfirmReading(section=k, adherence=adh, basis=basis, confirmed=conf, not_confirmed=failed,
                                  side_effects=side, note=note))
    return out
