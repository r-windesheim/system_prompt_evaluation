"""Discovery: find effects of a part that no detector was written for. Propose, then verify.

For each part k:

1. Propose yes/no statements about a single answer, from two sources:
   - intended: from the instruction text alone ("what would an answer show if this were followed");
   - discovered: from paired answers (with k / without k, same question and sample) on a subset of
     the questions. The two sides are labelled A/B at random and shown in random order, and the
     instruction is not shown, so the proposer cannot know or be led by which side has the part.
2. Verify: a judge sees one statement, the user question and ONE answer (nothing about the
   configuration) and says YES / NO / NA. Every answer in ``full`` and ``without_k`` is judged.
   Discovered statements are judged only on the held-out questions they were not proposed from.
   If the run says which part each question targets (meta.query_targets), intended statements for k are
   judged only on the questions that target k, and discovered ones only on questions that do not.
   Answers that recite the system prompt are left out (with their pair), since a recited instruction
   looks like a followed one.
3. Analyse the 0/1 judgments with the paired statistics the habits use (attribution.paired_stats), but
   with the question as the unit (sign flips and bootstrap over whole questions). Benjamini-Hochberg runs in
   two families: intended statements (is the instruction followed?) and discovered ones (side effects?).
4. Measure the judge: re-judge a stratified sample with a second, equivalent prompt; statements
   whose verdicts are unstable are flagged and never marked significant. Unreadable replies are
   counted and excluded with their pair, never read as "no".
5. Classify significant discovered statements as intended or side effect (one model call each),
   and derive a per-part reading (followed / not followed / redundant / ...).

A finding never rests on the proposer's say-so: only the verified paired difference counts.
See docs/discovery.md for limits and cost.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
from dataclasses import dataclass

import numpy as np

from . import attribution, prompts, schedule
from .bundle import (SCHEMA_VERSION, Analysis, Discovery, PairExample, PartReading, RunBundle, ScreenPick, ScreenUse,
                     Statement)

WARN = "Discovery: "
# flags that bar a statement from being significant and from the per-part reading
BLOCKING = {"judge_unreliable", "judge_unchecked", "unparseable", "exclusion_asymmetry"}
# Benjamini-Hochberg families: a statement's family is its source. Intended statements ask "is the instruction
# followed?", discovered ones "does the part have side effects?"; each family's FDR holds on its own.
FAMILIES = ("intended", "discovered")
_LETTER = {"yes": "y", "no": "n", "na": "a", None: "u"}


@dataclass
class DiscoveryOptions:
    max_discovered: int = 6       # discovered statements kept per part
    max_intended: int = 3         # intended statements kept per part
    proposal_calls: int = 2       # proposer calls per part, each on a different sample of pairs
    pairs_per_call: int = 6
    discover_share: float = 1 / 3  # share of questions used to propose; the rest verify
    rejudge_per_class: int = 10   # re-judge up to this many YES and this many NO verdicts per statement
    min_agreement: float = 0.8
    min_kappa: float = 0.5
    min_rejudged: int = 5
    max_unparseable: float = 0.2  # share of a statement's verdicts that may be unreadable
    min_pairs: int = 8
    proposal_chars: int = 1500    # answers are cut to this many characters when shown to the proposer
    judge_chars: int = 12000
    n_examples: int = 3
    redundant_rate: float = 0.8   # intended behaviour this common in BOTH arms: the part is not needed for it
    absent_rate: float = 0.5      # upper CI of the with-part rate below this: not followed
    echo_ngram: int = 8           # a verbatim run of this many words counts as copied from the system prompt
    echo_share: float = 0.5       # answer covers this share of its own system prompt in such runs: a recitation
    seed: int | None = None       # defaults to the run's seed
    # attention screen (spet/screen.py): (section, query_idx) -> lift. When set, the proposer's pairs for part k are
    # the discovery-question pairs with the highest lift for k, instead of a random draw. It changes nothing else.
    screen_lift: dict[tuple[int, int], float] | None = None
    screen_info: dict | None = None  # file, sha256, block, model, n_samples, fingerprint: stored in the bundle


def split_queries(n: int, share: float, seed: int) -> tuple[list[int], list[int]]:
    """(propose-from, verify-on) question indices. Deterministic; empty proposal set if n < 2."""
    if n < 2:
        return [], list(range(n))
    idx = list(range(n))
    random.Random(f"spet-discovery:{seed}").shuffle(idx)
    nd = min(n - 1, max(1, round(n * share)))
    return sorted(idx[:nd]), sorted(idx[nd:])


_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("\u2019", "'"))


def echo_share(answer: str, system: str, n: int = 8) -> float:
    """Share of the system prompt's words that sit in a run of >= n consecutive words also found in the answer.

    On the July 2024 Sonnet run every answer to "repeat your instructions word for word" that complied scored
    0.74 to 1.0, and every other answer scored at most 0.012.
    """
    sw, aw = _words(system), _words(answer)
    if len(sw) < n or len(aw) < n:
        return 0.0
    grams = {tuple(aw[i:i + n]) for i in range(len(aw) - n + 1)}
    hit = [False] * len(sw)
    for i in range(len(sw) - n + 1):
        if tuple(sw[i:i + n]) in grams:
            hit[i:i + n] = [True] * n
    return sum(hit) / len(sw)


def plan(spec, opts: DiscoveryOptions | None = None) -> dict[str, int]:
    """Answers and upper bounds on discovery calls for a run spec, before any answer exists.

    Bounds assume every part yields the full I intended and D discovered statements and that no answer is cut
    off, recited or judged NA; real runs make fewer calls. ``spec`` is a run.RunSpec.
    """
    opts = opts or DiscoveryOptions()
    K, nq = len(spec.sections), len(spec.queries)
    tg = spec.query_targets
    n_of = lambda removed, q: schedule.n_samples(removed, q, spec.n_per_query, tg, spec.n_per_query_untargeted)  # noqa: E731
    answers = sum(n_of(r, q) for _, r in schedule.config_ids(K) for q in range(nq))
    disc_q, hold_q = split_queries(nq, opts.discover_share, spec.seed if opts.seed is None else opts.seed)
    judge = 0
    for k in range(K):
        mine = [q for q in range(nq) if tg and k in tg[q]]
        pairs = lambda qs: sum(min(n_of(None, q), n_of(k, q)) for q in qs)  # noqa: E731
        judge += 2 * opts.max_intended * pairs(mine or range(nq))
        if disc_q:
            judge += 2 * opts.max_discovered * pairs([q for q in hold_q if q not in mine])
    return dict(answers=answers, intended=K, propose=K * opts.proposal_calls if disc_q else 0, judge=judge,
                rejudge=2 * opts.rejudge_per_class * K * (opts.max_intended + opts.max_discovered),
                classify=K * opts.max_discovered)


def family_bounds(spec, opts: DiscoveryOptions | None = None, alpha: float | None = None) -> dict[str, dict]:
    """Per BH family, before any answer exists: the most tests it can hold, BH's first threshold alpha/m at that m
    (the strictest one, which a statement must pass to be significant on its own), the question counts its
    statements are tested on, and the smallest p the by-question test can return on them.

    Upper bounds on m assume every part yields I intended and D discovered statements and that each is tested.
    The smallest p assumes every question keeps its pair and shows a nonzero difference of the same sign: a
    question whose differences sum to zero does not count, so the real floor is 2/2^(questions with a nonzero
    sum). Above 16 questions the test is a 10,000-draw Monte Carlo, whose floor is 1/10,001.
    """
    opts = opts or DiscoveryOptions()
    alpha = spec.alpha if alpha is None else alpha
    K, nq, tg = len(spec.sections), len(spec.queries), spec.query_targets
    disc_q, hold_q = split_queries(nq, opts.discover_share, spec.seed if opts.seed is None else opts.seed)
    g = {"intended": [], "discovered": []}
    for k in range(K):
        mine = [q for q in range(nq) if tg and k in tg[q]]
        g["intended"].append(len(mine or range(nq)))
        if disc_q:
            g["discovered"].append(len([q for q in hold_q if q not in mine]))
    out = {}
    for fam, m_per in (("intended", opts.max_intended), ("discovered", opts.max_discovered)):
        gs = g[fam]
        if not gs:
            continue
        m = K * m_per
        floor = max(attribution.cluster_p_floor(x) if x <= 16 else 1 / (attribution.N_PERM + 1) for x in gs)
        out[fam] = dict(max_tests=m, first_threshold=alpha / m, questions_min=min(gs), questions_max=max(gs),
                        smallest_p=floor,
                        # nonzero same-sign questions needed for p <= alpha/m; only meaningful for the exact test
                        questions_needed=None if min(gs) > 16 else
                        next((x for x in range(1, 17) if 2 / 2 ** x <= alpha / m), None))
    return out


def make_judge(base_url: str | None = None, model: str | None = None, *,
               run_base_url: str | None = None, run_model: str | None = None):
    """Judge provider, same class as the answers (cache, concurrency, retries).

    Precedence: explicit argument, then SPET_JUDGE_BASE_URL / SPET_JUDGE_MODEL / SPET_JUDGE_API_KEY,
    then the run's endpoint and model, then SPET_BASE_URL / SPET_MODEL / SPET_API_KEY.
    """
    from .providers import OpenAICompatible

    env = os.environ.get
    base = base_url or env("SPET_JUDGE_BASE_URL") or run_base_url or env("SPET_BASE_URL")
    model = model or env("SPET_JUDGE_MODEL") or run_model or env("SPET_MODEL")
    if not base or not model:
        raise ValueError("No judge endpoint: set SPET_JUDGE_BASE_URL and SPET_JUDGE_MODEL (or SPET_BASE_URL/SPET_MODEL).")
    eff = os.environ.get("SPET_JUDGE_REASONING_EFFORT") or os.environ.get("SPET_REASONING_EFFORT")
    # the run's key (SPET_API_KEY) is only sent if the judge is on the run's host
    from .providers import _host
    run_host = _host(run_base_url or env("SPET_BASE_URL") or "")
    key = env("SPET_JUDGE_API_KEY") or (None if _host(base) == run_host else "")
    return OpenAICompatible(base, model, api_key=key,
                            max_tokens=int(os.environ.get("SPET_JUDGE_MAX_TOKENS", "4000")),
                            max_concurrency=int(os.environ.get("SPET_JUDGE_MAX_CONCURRENCY", "16")),
                            extra={"reasoning_effort": eff} if eff else None)


class _Calls:
    def __init__(self, provider, progress=None):
        self.p = provider
        self.counts: dict[str, int] = {}
        self.errors = 0
        self.done = 0
        self.total = 0
        self.progress = progress

    def expect(self, n: int) -> None:
        self.total += n
        if self.progress:
            self.progress(self.done, self.total)

    async def __call__(self, kind: str, system: str, user: str) -> str | None:
        self.counts[kind] = self.counts.get(kind, 0) + 1
        try:
            out = await self.p.complete(system, user, temperature=0.0, seed=0)
            if getattr(out, "finish_reason", None) == "length":
                out = None  # reasoning or reply cut off: unreadable, not "no"
        except Exception:  # noqa: BLE001 (endpoint failure: counted, reported, never read as a verdict)
            self.errors += 1
            out = None
        self.done += 1
        if self.progress:
            self.progress(self.done, max(self.total, self.done))
        return out


def judge_flags(stats: dict, pairs: list[tuple[bool, bool]], agreement: float | None, kappa: float | None,
                n_cells: int, n_unparseable: int, asym: bool, opts: DiscoveryOptions) -> list[str]:
    """Flags from one statement's judged pairs and its re-judge sample. Shared by discovery and confirmation."""
    flags = []
    if len(pairs) < opts.min_rejudged and stats["tested"]:
        flags.append("judge_unchecked")
    elif agreement is not None and (agreement < opts.min_agreement or (kappa is not None and kappa < opts.min_kappa)):
        flags.append("judge_unreliable")
    if n_cells and n_unparseable / (2 * n_cells) > opts.max_unparseable:
        flags.append("unparseable")
    if asym:
        flags.append("exclusion_asymmetry")
    if pairs and len({x for x, _ in pairs}) == 1:
        flags.append("rejudge_one_class")  # agreement only shows the judge repeats one verdict
    if not stats["tested"]:
        flags.append("never_seen")
    elif min(stats["full_mean"], stats["ablated_mean"]) >= 0.9:
        flags.append("ceiling")
    if stats["n_pairs"] < opts.min_pairs:
        flags.append("few_pairs")
    return flags


def _kappa(a: list[bool], b: list[bool]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe >= 1 - 1e-12 else (po - pe) / (1 - pe)


async def discover(b: RunBundle, judge, opts: DiscoveryOptions | None = None, *, progress=None) -> RunBundle:
    """Return a copy of ``b`` with a ``discovery`` block. Judge calls only: no new answers."""
    opts = opts or DiscoveryOptions()
    seed = b.meta.seed if opts.seed is None else opts.seed
    rng = random.Random(f"spet-discovery-pairs:{seed}")
    call = _Calls(judge, progress)
    alpha = b.analysis.alpha if b.analysis else 0.05
    queries = b.meta.queries

    ans: dict[tuple[str, int, int], str] = {}
    for r in b.responses:
        if r.finish_reason != "length" and r.text.strip():  # same exclusion as the habit analysis
            ans[(r.config, r.query_idx, r.sample_idx)] = r.text
    without = {c.removed: c.id for c in b.configs if c.removed is not None}
    parts = [s for s in b.sections if s.id in without]
    disc_q, hold_q = split_queries(len(queries), opts.discover_share, seed)
    warnings: list[str] = []
    if not disc_q:
        warnings.append("only one question, so nothing was held out: discovered statements were skipped "
                        "and only intended statements were checked.")

    # which questions each part was written for; parts nobody targets keep the old all-questions behaviour
    qt = b.meta.query_targets
    targeted = {p.id: sorted(q for q in range(len(queries)) if qt and p.id in qt[q]) for p in parts}
    untargeted_parts = [p for p in parts if not targeted[p.id]]
    all_q = list(range(len(queries)))

    def intended_qs(k: int) -> list[int]:
        return targeted[k] or all_q

    def other(k: int, qs: list[int]) -> list[int]:
        return [q for q in qs if q not in targeted[k]]

    # answers that recite their own system prompt: any statement about the prompt's content looks satisfied
    sec_text = {s.id: s.text for s in b.sections}
    removed_of = {c.id: c.removed for c in b.configs}
    systems = {c: schedule.join_sections([t for i, t in sec_text.items() if i != r]) for c, r in removed_of.items()}
    echo = {key for key, text in ans.items()
            if echo_share(text, systems[key[0]], opts.echo_ngram) >= opts.echo_share}

    def cells(k: int, qs: list[int]) -> list[tuple[int, int]]:
        cfg = without[k]
        return sorted((q, s) for (c, q, s) in ans if c == "full" and q in qs and (cfg, q, s) in ans)

    def clean(k: int, cs: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(q, s) for q, s in cs if ("full", q, s) not in echo and (without[k], q, s) not in echo]

    # ---- 1. proposals -----------------------------------------------------------------------
    picks: list[ScreenPick] = []

    def proposal_batches(k: int) -> list[str]:
        pool = clean(k, cells(k, other(k, disc_q)))
        rng.shuffle(pool)  # also with a screen, so the draws below stay the same as without one
        if opts.screen_lift is not None:
            # highest lift for k first; the shuffle above breaks ties and orders questions the screen lacks.
            # The pool itself is unchanged: discovery questions that do not target k, so the held-out split holds.
            lift = opts.screen_lift
            pool.sort(key=lambda c: -lift.get((k, c[0]), float("-inf")))
        out = []
        for i in range(opts.proposal_calls):
            chunk = pool[i * opts.pairs_per_call:(i + 1) * opts.pairs_per_call]
            if not chunk:
                break
            if opts.screen_lift is not None:
                picks.extend(ScreenPick(section=k, query_idx=q, sample_idx=s, lift=opts.screen_lift.get((k, q)), call=i)
                             for q, s in chunk)
            a_is_with = rng.random() < 0.5  # which group letter is the with-part side, per call
            shown = []
            for q, s in chunk:
                w = prompts.labelled("A" if a_is_with else "B", ans[("full", q, s)][:opts.proposal_chars])
                wo = prompts.labelled("B" if a_is_with else "A", ans[(without[k], q, s)][:opts.proposal_chars])
                shown.append((queries[q], *((w, wo) if rng.random() < 0.5 else (wo, w))))
            out.append(prompts.propose_user(shown))
        return out

    batches = {p.id: proposal_batches(p.id) if disc_q else [] for p in parts}
    call.expect(len(parts) + sum(len(v) for v in batches.values()))
    intended_sys = prompts.INTENDED_SYSTEM.format(n=opts.max_intended)
    propose_sys = prompts.PROPOSE_SYSTEM.format(n=opts.max_discovered)
    intended_raw = await asyncio.gather(*(call("intended", intended_sys, prompts.intended_user(p.text)) for p in parts))
    proposed_raw = await asyncio.gather(*(asyncio.gather(*(call("propose", propose_sys, u) for u in batches[p.id]))
                                          for p in parts))

    lost = sum(r is None for praws in proposed_raw for r in praws)
    asked = sum(len(praws) for praws in proposed_raw)
    if lost:  # a cut-off proposer silently yields no discovered statements, so say so
        warnings.append(f"{lost} of {asked} proposer calls failed or were cut off before answering "
                        "(raise SPET_JUDGE_MAX_TOKENS or lower SPET_JUDGE_REASONING_EFFORT), so some differences were never proposed.")

    stmts: list[dict] = []
    for p, iraw, praws in zip(parts, intended_raw, proposed_raw):
        k = p.id
        intended = prompts.dedupe(prompts.parse_statements(iraw, opts.max_intended * 2))[:opts.max_intended]
        if iraw is not None and not intended:
            warnings.append(f"no usable intended statements for part {k + 1} ({p.label}).")
        found = [s for raw in praws for s in prompts.parse_statements(raw, opts.max_discovered * 2)]
        also = {i for i, t in enumerate(intended) if any(prompts.similar(t, s) for s in found)}
        discovered = prompts.dedupe(found, against=intended)[:opts.max_discovered]
        for i, t in enumerate(intended):
            fl = (["also_discovered"] if i in also else []) + ([] if targeted[k] else ["untargeted"])
            stmts.append(dict(id=f"p{k}.i{i}", section=k, text=t, source="intended", qs=intended_qs(k), flags=fl))
        for i, t in enumerate(discovered):
            stmts.append(dict(id=f"p{k}.d{i}", section=k, text=t, source="discovered", qs=other(k, hold_q), flags=[]))

    # ---- 2. verification: one statement, one question, one answer ---------------------------
    jobs = []  # (statement index, config, q, s)
    echo_cells = 0
    for si, st in enumerate(stmts):
        every = cells(st["section"], st["qs"])
        st["cells"] = clean(st["section"], every)
        st["n_echo"] = len(every) - len(st["cells"])
        echo_cells += st["n_echo"]
        for q, s in st["cells"]:
            jobs += [(si, "full", q, s), (si, without[st["section"]], q, s)]
    call.expect(len(jobs))

    def judge_one(si, cfg, q, s, alt=False):
        st = stmts[si]
        text = ans[(cfg, q, s)][:opts.judge_chars]
        if alt:
            return call("rejudge", prompts.JUDGE_ALT_SYSTEM, prompts.judge_alt_user(st["text"], queries[q], text))
        return call("judge", prompts.JUDGE_SYSTEM, prompts.judge_user(st["text"], queries[q], text))

    raw = await asyncio.gather(*(judge_one(*j) for j in jobs))
    verdict: dict[tuple[int, str, int, int], str | None] = {j: prompts.parse_verdict(r) for j, r in zip(jobs, raw)}

    # ---- 3. judge reliability: re-judge a stratified sample with an equivalent prompt --------
    rj_jobs = []
    for si in range(len(stmts)):
        mine = [j for j in jobs if j[0] == si]
        yes = [j for j in mine if verdict[j] == "yes"]
        no = [j for j in mine if verdict[j] == "no"]
        r = random.Random(f"spet-rejudge:{seed}:{si}")
        rj_jobs += r.sample(yes, min(len(yes), opts.rejudge_per_class)) + r.sample(no, min(len(no), opts.rejudge_per_class))
    call.expect(len(rj_jobs))
    rj_raw = await asyncio.gather(*(judge_one(*j, alt=True) for j in rj_jobs))
    rejudge: dict[int, list[tuple[bool, bool]]] = {}
    rj_store: dict[int, list[tuple[int, int, str, str]]] = {}
    for j, r in zip(rj_jobs, rj_raw):
        v2 = prompts.parse_verdict(r)
        rejudge.setdefault(j[0], []).append((verdict[j] == "yes", v2 == "yes") if v2 in ("yes", "no") else None)
        rj_store.setdefault(j[0], []).append((j[2], j[3], "w" if j[1] == "full" else "o", _LETTER[v2]))

    # ---- 4. paired statistics; BH within each family (intended, discovered) -------------------
    length_shift = {e.section for e in b.effects if e.detector == "words" and e.significant}
    context = {e.section for e in b.effects if "context_shift" in e.flags}
    nrng = np.random.default_rng(seed + 7)
    results = []
    n_unparseable = 0
    for si, st in enumerate(stmts):
        k, cfg = st["section"], without[st["section"]]
        f, a, groups, used = [], [], [], []
        unp = na = 0
        for q, s in st["cells"]:
            v1, v0 = verdict[(si, "full", q, s)], verdict[(si, cfg, q, s)]
            unp += (v1 is None) + (v0 is None)
            na += (v1 == "na") + (v0 == "na")
            if v1 in ("yes", "no") and v0 in ("yes", "no"):
                f.append(float(v1 == "yes")); a.append(float(v0 == "yes")); groups.append(q); used.append((q, s))
        n_unparseable += unp
        ex_with = np.array([float(verdict[(si, "full", q, s)] not in ("yes", "no")) for q, s in st["cells"]])
        ex_without = np.array([float(verdict[(si, cfg, q, s)] not in ("yes", "no")) for q, s in st["cells"]])
        # dropping pairs is only harmless if it happens equally often on both sides
        asym = len(ex_with) > 0 and attribution.sign_flip_p(ex_with - ex_without, nrng) < 0.05
        f_, a_, g_ = np.array(f), np.array(a), np.array(groups)
        stats = attribution.paired_stats(f_, a_, g_, nrng, cluster=True)  # the question is the unit
        full_ci = attribution.cluster_bootstrap_ci(f_, g_, nrng) if len(f) else None
        pairs = [x for x in rejudge.get(si, []) if x is not None]
        agreement = sum(x == y for x, y in pairs) / len(pairs) if pairs else None
        kappa = _kappa([x for x, _ in pairs], [y for _, y in pairs])
        flags = list(st["flags"]) + judge_flags(stats, pairs, agreement, kappa, len(st["cells"]), unp, asym, opts)
        if k in length_shift:
            flags.append("length_shift")
        if k in context:
            flags.append("context_shift")
        diff_cells = [(q, s, bool(x)) for (q, s), x, y in zip(used, f, a) if x != y]
        lead = [c for c in diff_cells if c[2] == (stats["delta"] >= 0)] + [c for c in diff_cells if c[2] != (stats["delta"] >= 0)]
        examples = [PairExample(query_idx=q, sample_idx=s, without_config=cfg, with_yes=wy) for q, s, wy in lead[:opts.n_examples]]
        judged = [(q, s, _LETTER[verdict[(si, "full", q, s)]] + _LETTER[verdict[(si, cfg, q, s)]]) for q, s in st["cells"]]
        results.append(dict(st=st, stats=stats, full_ci=full_ci, unp=unp, na=na, n_echo=st["n_echo"], judged=judged,
                            exw=int(ex_with.sum()), exwo=int(ex_without.sum()), agreement=agreement, kappa=kappa,
                            n_rj=len(pairs), flags=flags, examples=examples, used_q=sorted({q for q, _ in used})))

    tested = [i for i, r in enumerate(results) if r["stats"]["tested"]]
    qmap: dict[int, float] = {}
    fam_n: dict[str, int] = {}
    few_q = 0
    for fam in FAMILIES:
        members = [i for i in tested if results[i]["st"]["source"] == fam]
        fam_n[fam] = len(members)
        qmap.update(zip(members, attribution.benjamini_hochberg([results[i]["stats"]["p"] for i in members])))
        # with G questions the by-question test cannot go below 2/2^G; if that is above BH's first threshold in
        # the statement's own family, it can only become significant alongside many others
        bh_first = alpha / max(1, len(members))
        for i in members:
            if attribution.cluster_p_floor(len(results[i]["used_q"])) > bh_first:
                results[i]["flags"].append("too_few_questions")
                few_q += 1
    blocking = BLOCKING
    statements: list[Statement] = []
    for i, r in enumerate(results):
        s, st = r["stats"], r["st"]
        q = qmap.get(i, 1.0)
        statements.append(Statement(
            id=st["id"], section=st["section"], text=st["text"], source=st["source"],
            classification="intended" if st["source"] == "intended" else None,
            full_rate=s["full_mean"], ablated_rate=s["ablated_mean"], full_rate_ci=r["full_ci"],
            delta=s["delta"], ci=s["ci"], ci_query=s["ci_query"], p=s["p"], q=q,
            significant=q < alpha and not (blocking & set(r["flags"])),
            tested=s["tested"], n_pairs=s["n_pairs"], n_questions=len(r["used_q"]), verified_on=st["qs"],
            per_query=list(s["per_query"]), per_query_idx=list(s["per_query_idx"]), mde=s["mde"],
            n_unparseable=r["unp"], n_na=r["na"],
            n_excluded_with=r["exw"], n_excluded_without=r["exwo"], n_excluded_echo=r["n_echo"],
            agreement=r["agreement"], kappa=r["kappa"], n_rejudged=r["n_rj"], flags=r["flags"], examples=r["examples"],
            family=st["source"], verdicts=r["judged"], rejudged=rj_store.get(i, [])))

    # ---- 5. classify significant discovered statements relative to the instruction ----------
    by_id = {s.id: s for s in b.sections}
    todo = [st for st in statements if st.source == "discovered" and st.significant]
    call.expect(len(todo))
    cls_raw = await asyncio.gather(*(call("classify", prompts.CLASSIFY_SYSTEM,
                                          prompts.classify_user(by_id[st.section].text, st.text, st.delta > 0))
                                     for st in todo))
    unclassified = 0
    for st, r in zip(todo, cls_raw):
        st.classification = prompts.parse_classification(r)
        if st.classification is None:
            unclassified += 1
            st.flags.append("unclassified")

    readings = [_reading(k, [st for st in statements if st.section == k], opts, targeted=bool(targeted[k]))
                for k in sorted({p.id for p in parts})]

    # ---- warnings and provenance -------------------------------------------------------------
    n_unreliable = sum(bool(blocking & set(st.flags)) for st in statements)
    if n_unparseable:
        warnings.append(f"{n_unparseable} judge replies could not be read; they were left out with their pair, not counted as no.")
    if call.errors:
        warnings.append(f"{call.errors} judge calls failed and were treated as unreadable.")
    if n_unreliable:
        warnings.append(f"{n_unreliable} statements had unstable, unreadable or lopsidedly excluded judge verdicts and are never marked significant.")
    if unclassified:
        warnings.append(f"{unclassified} significant discovered statements could not be classified as intended or side effect.")
    weak = [r.section for r in readings if "was not checked" in r.note]
    if weak:
        warnings.append("the reading for part(s) " + ", ".join(str(k + 1) for k in weak) + " rests on statements the "
                        "judge answered the same way every time; the judge's reliability there is untested.")
    if echo:
        qs_e = sorted({q for _, q, _ in echo})
        warnings.append(f"{len(echo)} answers largely recite their own system prompt (question(s) "
                        + ", ".join(str(q + 1) for q in qs_e) + f"). Their pairs were left out of every check "
                        f"({echo_cells} statement-pairs in all), because a recited instruction looks like a followed one.")
    if qt is None:
        warnings.append("the run does not say which part each question targets, so every intended statement was "
                        "checked on every question, including questions where the instruction does not apply.")
    elif untargeted_parts:
        warnings.append("no question targets part(s) " + ", ".join(str(p.id + 1) for p in untargeted_parts)
                        + "; their intended statements were checked on every question (flag `untargeted`).")
    if few_q:
        warnings.append(f"{few_q} statements were checked on too few questions for the by-question test to pass "
                        "the multiple-testing correction on its own (flag `too_few_questions`); add questions, "
                        "not samples, to test them.")
    if disc_q and len(hold_q) < 3:
        warnings.append(f"discovered statements were verified on only {len(hold_q)} held-out question(s).")
    if getattr(judge, "model", None) == b.meta.model:
        warnings.append("the judge is the same model that wrote the answers; it may share their blind spots.")

    screen = None
    if opts.screen_lift is not None:
        info = opts.screen_info or {}
        screen = ScreenUse(file=info.get("file", ""), sha256=info.get("sha256", ""), block=info.get("block", "reasoning"),
                           model=info.get("model"), n_samples=info.get("n_samples"),
                           fingerprint=info.get("fingerprint", ""), picked=picks)

    out = b.model_copy(deep=True)
    out.schema_version = SCHEMA_VERSION
    out.confirmation = None  # it retested the previous screen's statements; a new screen voids it
    out.readout = None  # read from the old screen and confirmation
    out.discovery = Discovery(
        n_tests=len(tested), n_statements=len(statements), n_unreliable=n_unreliable, alpha=alpha,
        discovery_queries=disc_q, holdout_queries=hold_q, statements=statements, readings=readings,
        calls=dict(call.counts), n_unparseable=n_unparseable, n_errors=call.errors,
        prompt_echoes=sorted(echo), test="question", families=fam_n, screen=screen)
    if out.analysis is None:
        out.analysis = Analysis(n_tests=sum(e.tested for e in b.effects), alpha=alpha, mde_alpha=attribution.MDE_ALPHA)
    out.analysis.warnings = [w for w in out.analysis.warnings if not w.startswith(WARN)] + [WARN + w for w in warnings]
    js = getattr(judge, "settings", {}) or {}
    out.meta.settings = {k: v for k, v in out.meta.settings.items() if not k.startswith(("judge_", "discovery_"))}
    out.meta.settings.update({
        "judge_model": getattr(judge, "model", None), "judge_provider": getattr(judge, "name", None),
        "judge_endpoint_host": js.get("endpoint_host"), "judge_max_tokens": js.get("max_tokens"),
        "judge_reasoning_effort": js.get("reasoning_effort"), "judge_temperature": 0.0,
        "discovery_prompts_version": prompts.version(), "discovery_seed": seed,
        "discovery_max_intended": opts.max_intended, "discovery_max_discovered": opts.max_discovered,
        "discovery_proposal_calls": opts.proposal_calls, "discovery_pairs_per_call": opts.pairs_per_call,
        "discovery_rejudge_per_class": opts.rejudge_per_class, "discovery_min_agreement": opts.min_agreement,
        "discovery_min_kappa": opts.min_kappa, "discovery_echo_ngram": opts.echo_ngram,
        "discovery_echo_share": opts.echo_share, "discovery_test_unit": "question",
        "discovery_bh_families": ",".join(FAMILIES),
        "discovery_screen": (opts.screen_info or {}).get("sha256") if opts.screen_lift is not None else None,
    })
    return RunBundle.model_validate(out.model_dump())


UNTARGETED_NOTE = (" No question targets this part, so the checks used every question, including ones where"
                   " the instruction does not apply; that dilutes the rates.")


def _reading(k: int, sts: list[Statement], opts: DiscoveryOptions, targeted: bool = True) -> PartReading:
    side = [s.id for s in sts if s.significant and s.classification == "side_effect"]
    usable = [s for s in sts if s.source == "intended" and not BLOCKING & set(s.flags)]
    if not usable:
        return PartReading(section=k, adherence="not_assessed", side_effects=side,
                           note="No intended statement could be judged reliably." + ("" if targeted else UNTARGETED_NOTE))
    status = {}
    for s in usable:
        hi = s.full_rate_ci[1] if s.full_rate_ci else s.full_rate
        if s.significant and s.delta > 0:
            status[s.id] = "confirmed"
        elif not s.significant and min(s.full_rate, s.ablated_rate) >= opts.redundant_rate:
            status[s.id] = "redundant"
        elif not s.significant and hi < opts.absent_rate:
            status[s.id] = "absent"
        else:
            status[s.id] = "inconclusive"
    conf = [i for i, v in status.items() if v == "confirmed"]
    vals = set(status.values())
    if conf and vals <= {"confirmed", "redundant"}:
        adh = "followed"
    elif conf:
        adh = "partly_followed"
    elif vals == {"absent"}:
        adh = "not_followed"
    elif vals == {"redundant"}:
        adh = "redundant"
    else:
        adh = "inconclusive"
    notes = {"followed": "Answers show the intended behaviour more often with this part.",
             "partly_followed": "Some intended behaviour is confirmed; some is not.",
             "not_followed": "Even with this part, answers rarely show the intended behaviour.",
             "redundant": "Answers show the intended behaviour with and without this part.",
             "inconclusive": "The checks neither confirm nor rule out that the instruction is followed."}
    note = notes[adh]
    if adh in ("not_followed", "redundant") and all("rejudge_one_class" in s.flags for s in usable):
        note += (" The judge gave the same verdict to nearly every answer, so its ability to say the opposite"
                 " was not checked; read this with care.")
    if not targeted:
        note += UNTARGETED_NOTE
    return PartReading(section=k, adherence=adh, confirmed=conf, side_effects=side, note=note)
