"""Author-written statements: judge a supplied, pre-registered statement file against a finished bundle's answers.

The intended statements of discovery are written by the judge model from the instruction text. When those fail an
audit (compound, evaluative, uncheckable or misjudged), a person or a stronger model can write replacements from the
instruction text alone, blind to the answers, and save them before anything is judged. This module judges them:

- on the main run's stored answers, ``full`` and ``without_k``, on the part's targeted questions (all questions if
  the part has none), or on a subset the file names; no new answers are generated;
- with the blinded judge prompt, NA handling, recited-prompt exclusion and stratified re-judging of discovery, and
  the judge must be the screen's (model, host, max_tokens, reasoning effort, prompts);
- or, for a statement with a ``measure`` (only ``words`` for now), by the engine's word count instead of a judge.

They are **estimates** for the readout's first question ("does the model do it"): the with-part rate and its
by-question interval. They are kept out of the screen's Benjamini-Hochberg families and out of the confirmation's
candidate rule. The paired by-question p is recorded for information; no significance is claimed (``q`` is 1 and
``significant`` is false). A statement with ``polarity: reverse`` describes what the part asks the model not to do;
the readout reads compliance as 1 - the share judged yes. See docs/discovery.md, "Author-written statements".
"""

from __future__ import annotations

import asyncio
import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from . import attribution, detectors, prompts, schedule
from .bundle import SCHEMA_VERSION, Authored, PairExample, RunBundle, Statement
from .discovery import DiscoveryOptions, _Calls, _kappa, _LETTER, echo_share, judge_flags

NOTE = ("Author-written statements, judged on the main run's stored answers. Estimates for the readout's first "
        "question; not part of any Benjamini-Hochberg family or the confirmation rule. p is recorded for information "
        "only; no significance is claimed (q is fixed at 1).")
METRICS = {"words": detectors.word_count}


@dataclass
class Item:
    id: str
    section: int
    text: str
    polarity: str = "positive"
    measure: dict | None = None      # {"metric": "words", "max": 60} or {"metric": "words", "min": 150}
    queries: list[int] | None = None  # None: the part's targeted questions (all questions if it has none)


@dataclass
class AuthoredSpec:
    file: str
    sha256: str
    reviewer: str
    date: str
    items: list[Item]


def measure_text(m: dict) -> str:
    return " and ".join(f"{m['metric']} {op} {m[k]}" for k, op in (("min", ">="), ("max", "<=")) if k in m)


def holds(m: dict, text: str) -> bool:
    v = METRICS[m["metric"]](text)
    return ("min" not in m or v >= m["min"]) and ("max" not in m or v <= m["max"])


def load(path: str | Path, b: RunBundle) -> AuthoredSpec:
    """Read and check a statement file: ``reviewer``, ``date`` and ``statements: [{id, section, text, polarity,
    measure?, queries?}]``. ``section`` is a label or a 0-based id of a part the run removed."""
    path = Path(path)
    data = path.read_bytes()
    raw = yaml.safe_load(data) or {}
    rows = raw.get("statements")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path.name}: `statements` must be a non-empty list")
    by_label = {s.label: s.id for s in b.sections}
    removed = {c.removed for c in b.configs if c.removed is not None}
    targeted = _targeted(b)
    seen, items = set(), []
    for i, r in enumerate(rows):
        where = f"{path.name}: statement {i + 1}"
        if not isinstance(r, dict) or not r.get("id") or not str(r.get("text", "")).strip():
            raise ValueError(f"{where}: needs `id` and `text`")
        sid = str(r["id"])
        if sid in seen:
            raise ValueError(f"{where}: duplicate id {sid}")
        if b.discovery and sid in {s.id for s in b.discovery.statements}:
            raise ValueError(f"{where}: id {sid} is already a discovery statement")
        seen.add(sid)
        sec = r.get("section")
        k = by_label.get(sec, sec) if isinstance(sec, str) else sec
        if not isinstance(k, int) or k not in removed:
            raise ValueError(f"{where}: section {sec!r} is not a part the run removed")
        pol = r.get("polarity", "positive")
        if pol not in ("positive", "reverse"):
            raise ValueError(f"{where}: polarity must be positive or reverse")
        m = r.get("measure")
        if m is not None:
            if not isinstance(m, dict) or m.get("metric") not in METRICS or not ({"min", "max"} & set(m)) \
                    or set(m) - {"metric", "min", "max"}:
                raise ValueError(f"{where}: measure must be {{metric: words, min and/or max}}")
        qs = r.get("queries")
        if qs is not None:
            mine = set(targeted[k] or range(len(b.meta.queries)))
            if not isinstance(qs, list) or not qs or not set(qs) <= mine or len(set(qs)) != len(qs):
                raise ValueError(f"{where}: queries must be distinct questions the part is checked on")
            qs = sorted(qs)
        items.append(Item(id=sid, section=k, text=str(r["text"]).strip(), polarity=pol, measure=m, queries=qs))
    return AuthoredSpec(file=path.name, sha256=hashlib.sha256(data).hexdigest(), reviewer=str(raw.get("reviewer", "")),
                        date=str(raw.get("date", "")), items=items)


def _targeted(b: RunBundle) -> dict[int, list[int]]:
    qt = b.meta.query_targets
    return {s.id: [q for q in range(len(b.meta.queries)) if qt and s.id in qt[q]] for s in b.sections}


def _questions(it: Item, b: RunBundle, targeted: dict[int, list[int]]) -> list[int]:
    return it.queries if it.queries is not None else (targeted[it.section] or list(range(len(b.meta.queries))))


def _answers(b: RunBundle, keep_cut: bool) -> dict[tuple[str, int, int], str]:
    """Judged statements use discovery's exclusion (cut-off or empty answers out). A measured statement keeps a
    cut-off answer with text: it is long by construction, and dropping it would bias a length rate."""
    return {(r.config, r.query_idx, r.sample_idx): r.text for r in b.responses
            if r.text.strip() and (keep_cut or r.finish_reason != "length")}


def _cells(it: Item, b: RunBundle, ans: dict, qs: list[int]) -> list[tuple[int, int]]:
    wo = f"without_{it.section}"
    return sorted((q, s) for (c, q, s) in ans if c == "full" and q in qs and (wo, q, s) in ans)


def _echo(b: RunBundle, ans: dict, opts: DiscoveryOptions) -> set[tuple[str, int, int]]:
    if b.discovery is not None and b.discovery.prompt_echoes:
        stored = {tuple(e) for e in b.discovery.prompt_echoes}
    else:
        stored = set()
    sec = {s.id: s.text for s in b.sections}
    systems = {c.id: schedule.join_sections([t for i, t in sec.items() if i != c.removed]) for c in b.configs}
    # recompute (cut-off answers kept for measures are not in discovery's list) and add the stored ones
    return stored | {k for k, t in ans.items() if echo_share(t, systems[k[0]], opts.echo_ngram) >= opts.echo_share}


def plan(spec: AuthoredSpec, b: RunBundle, opts: DiscoveryOptions | None = None) -> dict:
    """Judge calls (upper bound: every usable pair, both sides) and re-judge calls (upper bound), before any call."""
    opts = opts or DiscoveryOptions()
    targeted = _targeted(b)
    judge = rejudge = measured = 0
    per = {}
    for it in spec.items:
        ans = _answers(b, keep_cut=it.measure is not None)
        echo = _echo(b, ans, opts)
        wo = f"without_{it.section}"
        cells = [(q, s) for q, s in _cells(it, b, ans, _questions(it, b, targeted))
                 if ("full", q, s) not in echo and (wo, q, s) not in echo]
        per[it.id] = len(cells)
        if it.measure is None:
            judge += 2 * len(cells)
            rejudge += min(2 * len(cells), 2 * opts.rejudge_per_class)
        else:
            measured += 2 * len(cells)
    return dict(judge=judge, rejudge=rejudge, measured=measured, pairs=per,
                judged_statements=sum(it.measure is None for it in spec.items),
                measured_statements=sum(it.measure is not None for it in spec.items))


async def judge_authored(b: RunBundle, spec: AuthoredSpec, judge, opts: DiscoveryOptions | None = None, *,
                         progress=None) -> RunBundle:
    """Return a copy of ``b`` with an ``authored`` block. Judge calls only (none for measured statements)."""
    opts = opts or DiscoveryOptions()
    seed = b.meta.seed if opts.seed is None else opts.seed
    queries = b.meta.queries
    targeted = _targeted(b)
    call = _Calls(judge, progress)
    work = []
    echo_all: set = set()
    for it in spec.items:
        ans = _answers(b, keep_cut=it.measure is not None)
        echo = _echo(b, ans, opts)
        echo_all |= {e for e in echo if e[1] in _questions(it, b, targeted)}
        wo = f"without_{it.section}"
        qs = _questions(it, b, targeted)
        every = _cells(it, b, ans, qs)
        cells = [(q, s) for q, s in every if ("full", q, s) not in echo and (wo, q, s) not in echo]
        work.append(dict(it=it, wo=wo, qs=qs, ans=ans, cells=cells, n_echo=len(every) - len(cells)))

    def judge_one(i, cfg, q, s, alt=False):
        w = work[i]
        text, stmt = w["ans"][(cfg, q, s)][:opts.judge_chars], w["it"].text  # the statement text, verbatim
        if alt:
            return call("rejudge", prompts.JUDGE_ALT_SYSTEM, prompts.judge_alt_user(stmt, queries[q], text))
        return call("judge", prompts.JUDGE_SYSTEM, prompts.judge_user(stmt, queries[q], text))

    jobs = [(i, cfg, q, s) for i, w in enumerate(work) if w["it"].measure is None
            for q, s in w["cells"] for cfg in ("full", w["wo"])]
    call.expect(len(jobs))
    raw = await asyncio.gather(*(judge_one(*j) for j in jobs))
    verdict = {j: prompts.parse_verdict(r) for j, r in zip(jobs, raw)}
    for i, w in enumerate(work):  # measured statements: the metric decides, never unreadable
        if w["it"].measure is not None:
            for q, s in w["cells"]:
                for cfg in ("full", w["wo"]):
                    verdict[(i, cfg, q, s)] = "yes" if holds(w["it"].measure, w["ans"][(cfg, q, s)]) else "no"

    rj_jobs = []
    for i, w in enumerate(work):
        if w["it"].measure is not None:
            continue
        mine = [j for j in jobs if j[0] == i]
        yes = [j for j in mine if verdict[j] == "yes"]
        no = [j for j in mine if verdict[j] == "no"]
        r = random.Random(f"spet-authored-rejudge:{seed}:{w['it'].id}")
        rj_jobs += r.sample(yes, min(len(yes), opts.rejudge_per_class)) + r.sample(no, min(len(no), opts.rejudge_per_class))
    call.expect(len(rj_jobs))
    rj_raw = await asyncio.gather(*(judge_one(*j, alt=True) for j in rj_jobs))
    rejudge: dict[int, list] = {}
    rj_store: dict[int, list] = {}
    for j, r in zip(rj_jobs, rj_raw):
        v2 = prompts.parse_verdict(r)
        rejudge.setdefault(j[0], []).append((verdict[j] == "yes", v2 == "yes") if v2 in ("yes", "no") else None)
        rj_store.setdefault(j[0], []).append((j[2], j[3], "w" if j[1] == "full" else "o", _LETTER[v2]))

    nrng = np.random.default_rng(seed + 11)
    statements, n_unp = [], 0
    for i, w in enumerate(work):
        it, wo, cells = w["it"], w["wo"], w["cells"]
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
        if it.measure is None:
            pairs = [x for x in rejudge.get(i, []) if x is not None]
            agreement = sum(x == y for x, y in pairs) / len(pairs) if pairs else None
            kappa = _kappa([x for x, _ in pairs], [y for _, y in pairs])
            flags = judge_flags(stats, pairs, agreement, kappa, len(cells), unp, asym, opts)
        else:  # no judge: only the data flags apply
            agreement = kappa = None
            pairs = []
            flags = [fl for fl in judge_flags(stats, [], None, None, len(cells), 0, False, opts)
                     if fl not in ("judge_unchecked",)]
        diff = [(q, s, bool(x)) for (q, s), x, y in zip(used, f, a) if x != y]
        lead = [c for c in diff if c[2] == (stats["delta"] >= 0)] + [c for c in diff if c[2] != (stats["delta"] >= 0)]
        statements.append(Statement(
            id=it.id, section=it.section, text=it.text, source="authored", classification=None,
            full_rate=stats["full_mean"], ablated_rate=stats["ablated_mean"], full_rate_ci=full_ci,
            delta=stats["delta"], ci=stats["ci"], ci_query=stats["ci_query"], p=stats["p"], q=1.0, significant=False,
            tested=stats["tested"], n_pairs=stats["n_pairs"], n_questions=len({q for q, _ in used}), verified_on=w["qs"],
            per_query=list(stats["per_query"]), per_query_idx=list(stats["per_query_idx"]), mde=stats["mde"],
            n_unparseable=unp, n_na=na, n_excluded_with=int(ex_w.sum()), n_excluded_without=int(ex_o.sum()),
            n_excluded_echo=w["n_echo"], agreement=agreement, kappa=kappa, n_rejudged=len(pairs), flags=flags,
            examples=[PairExample(query_idx=q, sample_idx=s, without_config=wo, with_yes=wy)
                      for q, s, wy in lead[:opts.n_examples]],
            family=None, polarity=it.polarity, measure=measure_text(it.measure) if it.measure else None,
            verdicts=[(q, s, _LETTER[verdict[(i, "full", q, s)]] + _LETTER[verdict[(i, wo, q, s)]]) for q, s in cells],
            rejudged=rj_store.get(i, [])))

    warnings = []
    if n_unp:
        warnings.append(f"{n_unp} judge replies could not be read; they were left out with their pair, not counted as no.")
    if call.errors:
        warnings.append(f"{call.errors} judge calls failed and were treated as unreadable.")
    if echo_all:
        warnings.append(f"{len(echo_all)} answers recite their own system prompt; their pairs were left out.")
    blocked = [st.id for st in statements if {"judge_unreliable", "judge_unchecked", "unparseable",
                                              "exclusion_asymmetry", "few_pairs"} & set(st.flags)]
    if blocked:
        warnings.append("not usable by the readout (flags): " + ", ".join(blocked))
    js = getattr(judge, "settings", {}) or {}
    settings = {
        "judge_model": getattr(judge, "model", None), "judge_provider": getattr(judge, "name", None),
        "judge_endpoint_host": js.get("endpoint_host"), "judge_max_tokens": js.get("max_tokens"),
        "judge_reasoning_effort": js.get("reasoning_effort"), "judge_temperature": 0.0,
        "discovery_prompts_version": prompts.version(), "rejudge_per_class": opts.rejudge_per_class,
        "min_agreement": opts.min_agreement, "min_kappa": opts.min_kappa, "min_pairs": opts.min_pairs,
        "echo_ngram": opts.echo_ngram, "echo_share": opts.echo_share, "rejudge_seed": seed,
        "test_rng_seed": seed + 11, "detector_version": detectors.detector_version(),
    }
    out = b.model_copy(deep=True)
    out.schema_version = SCHEMA_VERSION
    out.readout = None  # read without these statements; rerun `spet readout`
    out.authored = Authored(file=spec.file, sha256=spec.sha256, reviewer=spec.reviewer, date=spec.date,
                            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), statements=statements,
                            calls=dict(call.counts), n_unparseable=n_unp, n_errors=call.errors, warnings=warnings,
                            settings=settings, note=NOTE)
    return RunBundle.model_validate(out.model_dump())
