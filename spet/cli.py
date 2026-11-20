"""spet CLI.

    python -m spet run examples/stub-demo.yaml -o web/public/runs/stub-demo.json
    python -m spet validate web/public/runs/*.json
    python -m spet schema > docs/run-bundle.schema.json
    python -m spet discover runs/x.json -o runs/x.json     # judge calls only, no new answers
    python -m spet plan examples/sonnet35-july2024.yaml    # planned answers and judge calls, no model calls
    python -m spet confirm runs/x.json confirm.yaml -o runs/x-confirmed.json   # retest screen candidates
    python -m spet readout runs/x.json -o runs/x-read.json --audit audit.yaml   # per-part reading, no model calls
    python -m spet authored runs/x.json statements.yaml -o runs/x-auth.json   # judge author-written statements
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml

from . import bundle
from .providers import OpenAICompatible, StubProvider
from .run import RunSpec, execute
from .stub import respond

# Concrete, context-bearing tasks. The legacy defaults ("Should I do this?") were
# context-free, so every answer became a clarification request (audit M2).
DEFAULT_QUERIES = [
    "Rewrite this so it sounds professional: 'hey, the report is late again, need it by fri'",
    "My Python script fails with ModuleNotFoundError: No module named 'requests'. What should I do?",
    "Explain the difference between a process and a thread.",
    "I have a job offer with a higher salary but a longer commute. How should I decide?",
    "Summarise the main causes of inflation in two or three sentences.",
]


def _parse_queries(items: list, labels: list[str]) -> tuple[list[str], list[list[int]] | None]:
    """Queries are strings, or mappings ``{text: ..., targets: [...]}``. A target is a section label or a
    0-based section id; ``targets: []`` (or a plain string) means the question targets no part. Returns
    (texts, targets), with targets None when no query declares any. Raises ValueError (the server's 400)."""
    by_label = {lb: i for i, lb in enumerate(labels)}
    texts, targets, declared = [], [], False
    for i, it in enumerate(items):
        if isinstance(it, str):
            texts.append(it)
            targets.append([])
            continue
        if not isinstance(it, dict) or "text" not in it:
            raise ValueError(f"query {i + 1}: expected a string or a mapping with 'text'")
        texts.append(str(it["text"]))
        raw_t = it.get("targets", [])
        raw_t = [raw_t] if isinstance(raw_t, (str, int)) else list(raw_t or [])
        ids = []
        for t in raw_t:
            if isinstance(t, int) and 0 <= t < len(labels):
                ids.append(t)
            elif isinstance(t, str) and t in by_label:
                ids.append(by_label[t])
            else:
                raise ValueError(f"query {i + 1}: unknown target {t!r} (use a section label or a 0-based id)")
        declared = declared or "targets" in it
        targets.append(sorted(set(ids)))
    return texts, (targets if declared else None)


def load_spec(path: Path) -> tuple[RunSpec, dict]:
    raw = yaml.safe_load(path.read_text())
    secs = raw["sections"]
    labels = [s.get("label", f"Section {i + 1}") if isinstance(s, dict) else f"Section {i + 1}"
              for i, s in enumerate(secs)]
    try:
        queries, targets = _parse_queries(raw.get("queries") or DEFAULT_QUERIES, labels)
    except ValueError as e:
        raise SystemExit(str(e))
    n_u = raw.get("n_per_query_untargeted")
    spec = RunSpec(
        id=raw.get("id", path.stem),
        title=raw.get("title", path.stem),
        sections=[s["text"] if isinstance(s, dict) else s for s in secs],
        section_labels=labels,
        queries=queries,
        query_targets=targets,
        n_per_query_untargeted=None if n_u is None else int(n_u),
        n_per_query=int(raw.get("n_per_query", 8)),
        temperature=float(raw.get("temperature", 0.7)),
        seed=int(raw.get("seed", 0)),
        alpha=float(raw.get("alpha", 0.05)),
        notes=raw.get("notes", ""),
        fixture=bool(raw.get("fixture", False)),
    )
    return spec, raw.get("provider", {"kind": "stub"})


def make_provider(cfg: dict):
    kind = cfg.get("kind", "stub")
    if kind == "stub":
        return StubProvider(respond, model="stub-planted-v1")
    if kind == "openai":
        return OpenAICompatible(base_url=cfg["base_url"], model=cfg["model"],
                                max_concurrency=int(cfg.get("max_concurrency", 16)),
                                max_tokens=int(cfg.get("max_tokens", 1500)),
                                extra=cfg.get("extra"))
    raise SystemExit(f"unknown provider kind: {kind}")


def make_judge(pcfg: dict, args=None):
    """Stub runs get the stub judge unless --judge-base-url is given (env vars never send stub answers out).
    Otherwise: flags, then SPET_JUDGE_* env vars, then the run's endpoint and model."""
    from .discovery import make_judge as _make

    base, model = getattr(args, "judge_base_url", None), getattr(args, "judge_model", None)
    if getattr(args, "stub_judge", False) or (pcfg.get("kind", "stub") == "stub" and not base):
        return StubProvider(respond, model="stub-judge-v1")
    return _make(base, model, run_base_url=pcfg.get("base_url"), run_model=pcfg.get("model"))


def _discovery_options(args, b=None):
    """Discovery options from the flags. With ``--screen``, ``b`` (the bundle) is needed to check the screen fits."""
    from .discovery import DiscoveryOptions

    o = DiscoveryOptions()
    for name in ("max_discovered", "max_intended", "proposal_calls", "pairs_per_call", "rejudge_per_class"):
        v = getattr(args, name, None)
        if v is not None:
            setattr(o, name, v)
    path = getattr(args, "screen", None)
    if path and b is not None:
        from . import screen as S

        try:
            sc, sha = S.load(path)
            S.check(sc, [s.text for s in b.sections], b.meta.queries)
        except (OSError, ValueError) as e:
            raise SystemExit(f"--screen: {e}")
        block = getattr(args, "screen_block", None) or "reasoning"
        o.screen_lift = S.lifts(sc, block)
        o.screen_info = dict(file=Path(path).name, sha256=sha, block=block, model=sc.get("model"),
                             n_samples=sc.get("n_samples"), fingerprint=sc["fingerprint"])
    return o


async def _run_discovery(b, judge, args):
    from .discovery import discover

    def progress(done, total):
        if done == total or done % max(1, total // 20) == 0:
            print(f"\r  {done}/{total} judge calls", end="", file=sys.stderr, flush=True)

    try:
        return await discover(b, judge, _discovery_options(args, b), progress=progress)
    finally:
        print(file=sys.stderr)
        if hasattr(judge, "aclose"):
            await judge.aclose()


def _print_discovery(b) -> None:
    d = b.discovery
    if not d:
        return
    print(f"discovery: {d.n_statements} statements, {d.n_tests} tested, "
          f"{sum(s.significant for s in d.statements)} significant, {d.n_unreliable} unreliable; "
          f"calls {d.calls}", file=sys.stderr)
    for s in sorted((s for s in d.statements if s.significant), key=lambda s: s.q):
        print(f"  part {s.section + 1} {s.classification or '?':<11} {s.full_rate:.2f} vs {s.ablated_rate:.2f}  "
              f"q={s.q:.3g}  {s.text}", file=sys.stderr)
    for r in d.readings:
        print(f"  part {r.section + 1}: {r.adherence}", file=sys.stderr)


def cmd_discover(args) -> int:
    b = bundle.load(args.bundle)
    # the bundle stores only the endpoint host, so the judge URL comes from flags or env; the model defaults to the run's
    pcfg = {"kind": "stub"} if b.meta.provider == "stub" else {"kind": "openai", "model": b.meta.model}
    try:
        judge = make_judge(pcfg, args)
    except ValueError as e:
        raise SystemExit(str(e))
    out_b = asyncio.run(_run_discovery(b, judge, args))
    out = Path(args.out or args.bundle)
    bundle.dump(out_b, out)
    print(f"wrote {out}", file=sys.stderr)
    _print_discovery(out_b)
    return 0


def cmd_run(args) -> int:
    spec, pcfg = load_spec(Path(args.spec))
    provider = make_provider(pcfg)

    def progress(done, total):
        if done == total or done % max(1, total // 20) == 0:
            print(f"\r  {done}/{total} responses", end="", file=sys.stderr, flush=True)

    async def go():
        try:
            return await execute(spec, provider, progress=progress)
        finally:
            if hasattr(provider, "aclose"):
                await provider.aclose()

    b = asyncio.run(go())
    print(file=sys.stderr)
    if args.discover:
        b = asyncio.run(_run_discovery(b, make_judge(pcfg, args), args))
    out = Path(args.out or f"{spec.id}.json")
    bundle.dump(b, out)
    sig = [e for e in b.effects if e.significant]
    print(f"wrote {out}: {len(b.responses)} responses, {len(sig)} significant effects", file=sys.stderr)
    for e in sorted(sig, key=lambda e: e.q)[:10]:
        print(f"  {e.detector:<14} section {e.section}  delta {e.delta:+.2f}  "
              f"CI [{e.ci[0]:+.2f}, {e.ci[1]:+.2f}]  q={e.q:.3g}", file=sys.stderr)
    _print_discovery(b)
    return 0


def cmd_plan(args) -> int:
    from .discovery import family_bounds, plan

    spec, _ = load_spec(Path(args.spec))
    opts = _discovery_options(args)
    p = plan(spec, opts)
    tg = spec.query_targets
    print(f"{len(spec.queries)} questions, {len(spec.sections)} parts, "
          f"{sum(bool(t) for t in tg) if tg else 0} questions with targets")
    print(f"answers: {p['answers']}")
    print("discovery calls (upper bounds): " + ", ".join(f"{k} {v}" for k, v in p.items() if k != "answers")
          + f"; total {sum(v for k, v in p.items() if k != 'answers')}")
    for fam, f in family_bounds(spec, opts).items():
        need = f["questions_needed"]
        print(f"{fam} family: at most {f['max_tests']} tests, first BH threshold alpha/m = {f['first_threshold']:.3g}; "
              f"tested on {f['questions_min']}-{f['questions_max']} questions, smallest p {f['smallest_p']:.3g}"
              + (f"; alone, a statement needs {need} questions with a same-signed difference" if need else ""))
    return 0


def cmd_confirm(args) -> int:
    from . import confirm as C

    b = bundle.load(args.bundle)
    try:
        cands = C.select(b)
        spec = C.load_spec(args.spec, b)
        C.check_spec(spec, b, cands)
        C.check_provider(spec.provider, b)
        pcfg = spec.provider if spec.provider.get("kind", "stub") != "stub" else {"kind": "stub"}
        judge = make_judge(pcfg, args)
        js = C.check_judge(judge, b)
    except ValueError as e:
        raise SystemExit(f"confirm: {e}")
    print("judge (matches the screen): " + ", ".join(f"{k}={v}" for k, v in js.items()), file=sys.stderr)
    r = C.RULE
    print(f"rule: intended p < {r.intended_p_below}, discovered p < {r.discovered_p_below}, tested, none of "
          f"{', '.join(r.excluded_flags)}", file=sys.stderr)
    print(f"selected {len(cands)} candidates:", file=sys.stderr)
    for st in cands:
        print(f"  {st.id:<8} {st.source:<10} part {st.section + 1} ({b.sections[st.section].label}): "
              f"{st.full_rate:.2f} vs {st.ablated_rate:.2f}, p={st.p:.3g}, q={st.q:.3g}  {st.text}", file=sys.stderr)
    p = C.plan(spec, b, cands)
    n_t = sum(bool(t) for t in spec.targets)
    print(f"plan: {len(spec.queries)} fresh questions ({n_t} targeted x {spec.n_per_query} samples, "
          f"{len(spec.queries) - n_t} general x {spec.n_per_query_general}), seed {spec.seed}; "
          f"answers {p['answers']}, judge calls <= {p['judge']}, re-judge calls <= {p['rejudge']}", file=sys.stderr)
    over = []
    if args.max_answers is not None and p["answers"] > args.max_answers:
        over.append(f"{p['answers']} answers > {args.max_answers}")
    if args.max_judge_calls is not None and p["judge"] + p["rejudge"] > args.max_judge_calls:
        over.append(f"{p['judge'] + p['rejudge']} judge calls > {args.max_judge_calls}")
    if over:
        raise SystemExit("confirm: over budget: " + "; ".join(over))
    if args.plan:
        if hasattr(judge, "aclose"):
            asyncio.run(judge.aclose())
        return 0
    provider = make_provider(spec.provider)

    def progress(what):
        def f(done, total):
            if done == total or done % max(1, total // 20) == 0:
                print(f"\r  {done}/{total} {what}", end="", file=sys.stderr, flush=True)
        return f

    async def go():
        try:
            return await C.confirm(b, spec, provider, judge, progress=progress("answers"),
                                   judge_progress=progress("judge calls"))
        finally:
            print(file=sys.stderr)
            for x in (provider, judge):
                if hasattr(x, "aclose"):
                    await x.aclose()

    out_b = asyncio.run(go())
    c = out_b.confirmation
    if c.n_errors and not args.keep_failed_calls:
        # resume = rerun the same command (answers and verdicts are cached); never write a partial result
        raise SystemExit(f"confirm: {c.n_errors} judge calls failed; nothing written. Rerun the same command to resume.")
    out = Path(args.out)
    bundle.dump(out_b, out)
    print(f"wrote {out}: {len(c.responses)} answers, calls {c.calls}", file=sys.stderr)
    for st in c.candidates:
        print(f"  {st.id:<8} {'CONFIRMED' if st.confirmed else 'not confirmed':<13} {st.full_rate:.2f} vs "
              f"{st.ablated_rate:.2f} (screen {st.screen_full_rate:.2f} vs {st.screen_ablated_rate:.2f}), "
              f"p={st.p:.3g}, q={st.q:.3g}, {st.n_questions} questions, flags {st.flags}", file=sys.stderr)
    for rd in c.readings:
        print(f"  part {rd.section + 1}: {rd.adherence} ({rd.basis})", file=sys.stderr)
    for w in c.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    return 0


def cmd_authored(args) -> int:
    from . import authored as A
    from . import confirm as C

    b = bundle.load(args.bundle)
    if not b.discovery:
        raise SystemExit("authored: the bundle has no discovery block (its judge settings are the reference)")
    try:
        spec = A.load(args.statements, b)
        if b.meta.provider == "stub":
            pcfg = {"kind": "stub"}
        else:
            base = args.judge_base_url or os.environ.get("SPET_JUDGE_BASE_URL") or os.environ.get("SPET_BASE_URL")
            if not base:
                raise ValueError("no judge endpoint: give --judge-base-url or set SPET_JUDGE_BASE_URL")
            pcfg = {"kind": "openai", "base_url": base, "model": b.meta.model}
        judge = make_judge(pcfg, args)
        js = C.check_judge(judge, b)
    except ValueError as e:
        raise SystemExit(f"authored: {e}")
    print("judge (matches the screen): " + ", ".join(f"{k}={v}" for k, v in js.items()), file=sys.stderr)
    p = A.plan(spec, b)
    print(f"{spec.file} (sha256 {spec.sha256[:12]}, {spec.reviewer}, {spec.date}): {len(spec.items)} statements, "
          f"{p['judged_statements']} judged, {p['measured_statements']} measured", file=sys.stderr)
    for it in spec.items:
        how = A.measure_text(it.measure) if it.measure else "judge"
        print(f"  {it.id:<7} part {it.section + 1:>2} {it.polarity:<8} {how:<14} {p['pairs'][it.id]:>3} pairs  "
              f"{it.text[:70]}", file=sys.stderr)
    total = p["judge"] + p["rejudge"]
    print(f"plan: judge calls <= {p['judge']}, re-judge calls <= {p['rejudge']} (total <= {total}); "
          f"{p['measured']} answers measured without a judge; no answers generated", file=sys.stderr)
    if args.max_judge_calls is not None and total > args.max_judge_calls:
        raise SystemExit(f"authored: over budget: {total} judge calls > {args.max_judge_calls}")
    if args.plan:
        if hasattr(judge, "aclose"):
            asyncio.run(judge.aclose())
        return 0

    def progress(done, total):
        if done == total or done % max(1, total // 20) == 0:
            print(f"\r  {done}/{total} judge calls", end="", file=sys.stderr, flush=True)

    async def go():
        try:
            return await A.judge_authored(b, spec, judge, progress=progress)
        finally:
            print(file=sys.stderr)
            if hasattr(judge, "aclose"):
                await judge.aclose()

    out_b = asyncio.run(go())
    a = out_b.authored
    if a.n_errors and not args.keep_failed_calls:
        raise SystemExit(f"authored: {a.n_errors} judge calls failed; nothing written. Rerun the same command to resume.")
    out = Path(args.out)
    bundle.dump(out_b, out)
    print(f"wrote {out}: calls {a.calls}", file=sys.stderr)
    for st in a.statements:
        ci = f"[{st.full_rate_ci[0]:.2f}, {st.full_rate_ci[1]:.2f}]" if st.full_rate_ci else "[-]"
        print(f"  {st.id:<7} yes {st.full_rate:.2f} {ci} vs {st.ablated_rate:.2f} ({st.polarity}), p={st.p:.3g} "
              f"(information only), {st.n_questions} q, {st.n_pairs} pairs, agreement {st.agreement}, "
              f"flags {st.flags}", file=sys.stderr)
    for w in a.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    return 0


def cmd_readout(args) -> int:
    from . import readout as R

    b = bundle.load(args.bundle)
    audit = rec = notes = nrec = None
    try:
        if args.audit:
            audit, rec = R.load_audit(args.audit, b)
        if args.annotations:
            notes, nrec = R.load_annotations(args.annotations, b)
        out_b = R.readout(b, audit, rec, notes, nrec)
    except ValueError as e:
        raise SystemExit(f"readout: {e}")
    out = Path(args.out)
    bundle.dump(out_b, out)
    ro = out_b.readout
    print(f"wrote {out}" + (f" (audit {rec.file}: {len(rec.valid)} valid, {len(rec.invalid)} invalid)" if rec else ""),
          file=sys.stderr)
    for p in ro.parts:
        print(f"  part {p.section + 1:>2} {b.sections[p.section].label:<30} {p.reading:<16} (was {p.adherence})",
              file=sys.stderr)
        for c in p.checks:
            ci = f"[{c.rate_with_ci[0]:.2f}, {c.rate_with_ci[1]:.2f}]" if c.rate_with_ci else "[-]"
            print(f"       {c.id:<7} {c.does:<9} {c.cause:<10} {c.rate_with:.2f} {ci} vs {c.rate_without:.2f}  "
                  f"{c.n_questions} q, {c.n_answers} answers, {c.data}  {c.text[:60]}", file=sys.stderr)
        for e in p.excluded:
            print(f"       {e.id:<7} left out: {e.reason[:100]}", file=sys.stderr)
    return 0


def cmd_label(args) -> int:
    from . import confirm as C
    from . import label as L

    b = bundle.load(args.bundle)
    if not b.readout:
        raise SystemExit("label: the bundle has no readout; run `spet readout` first (labels are for its checks)")
    ids = L.targets(b)
    try:
        if b.meta.provider == "stub":
            pcfg = {"kind": "stub"}
        else:
            base = args.judge_base_url or os.environ.get("SPET_JUDGE_BASE_URL") or os.environ.get("SPET_BASE_URL")
            if not base:
                raise ValueError("no judge endpoint: give --judge-base-url or set SPET_JUDGE_BASE_URL")
            pcfg = {"kind": "openai", "base_url": base, "model": b.meta.model}
        judge = make_judge(pcfg, args)
        if b.discovery and b.meta.provider != "stub":
            js = C.check_judge(judge, b)
            print("judge (matches the run's): " + ", ".join(f"{k}={v}" for k, v in js.items()), file=sys.stderr)
    except ValueError as e:
        raise SystemExit(f"label: {e}")
    print(f"{len(ids)} statements in the readout; at most {2 * len(ids)} label calls"
          + (f", capped at {args.max_calls}" if args.max_calls is not None else ""), file=sys.stderr)

    async def go():
        try:
            return await L.label_bundle(b, judge, force=args.force, max_calls=args.max_calls)
        finally:
            if hasattr(judge, "aclose"):
                await judge.aclose()

    out_b, rep_ = asyncio.run(go())
    out = Path(args.out)
    bundle.dump(out_b, out)
    print(f"wrote {out}: {rep_['calls']} label calls, {len(rep_['labels'])} labelled, {len(rep_['failed'])} failed, "
          f"{len(rep_['skipped'])} over budget", file=sys.stderr)
    for sid, lab in rep_["labels"].items():
        print(f"  {sid:<7} {lab if lab else '(none: ' + rep_['failed'].get(sid, '') + ')'}", file=sys.stderr)
    return 0


def cmd_validate(args) -> int:
    bad = 0
    for p in args.paths:
        try:
            b = bundle.load(p)
            print(f"ok   {p}  ({len(b.responses)} responses, {len(b.effects)} effects)")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"FAIL {p}: {e}")
    return 1 if bad else 0


def cmd_rescore(args) -> int:
    from .run import rescore

    b = rescore(bundle.load(args.bundle))
    out = Path(args.out or args.bundle)
    bundle.dump(b, out)
    sig = [e for e in b.effects if e.significant]
    print(f"wrote {out}: {len(sig)} significant effects, {b.analysis.n_tests} habit tests", file=sys.stderr)
    for w in b.analysis.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    from .server import create_app

    uvicorn.run(create_app(Path(args.runs_dir)), host="127.0.0.1", port=args.port)
    return 0


def cmd_mock(args) -> int:
    import uvicorn

    from .mock import create_mock

    uvicorn.run(create_mock(), host="127.0.0.1", port=args.port)
    return 0


def _judge_args(p) -> None:
    p.add_argument("--judge-base-url", help="judge endpoint (default: SPET_JUDGE_BASE_URL, else the run's)")
    p.add_argument("--judge-model", help="judge model (default: SPET_JUDGE_MODEL, else the run's)")
    p.add_argument("--stub-judge", action="store_true", help="use the deterministic stub judge (no model calls)")
    p.add_argument("--max-discovered", type=int)
    p.add_argument("--max-intended", type=int)
    p.add_argument("--proposal-calls", type=int)
    p.add_argument("--pairs-per-call", type=int)
    p.add_argument("--rejudge-per-class", type=int)
    p.add_argument("--screen", help="attention screen file (deploy/modal_attention.py::screen): show the proposer the "
                                    "discovery pairs with the highest lift for each part first, instead of a random draw")
    p.add_argument("--screen-block", choices=["reasoning", "answer"], default="reasoning",
                   help="rank by the lift on reasoning tokens (default) or on answer tokens")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spet")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="execute a run spec and write a bundle")
    r.add_argument("spec")
    r.add_argument("-o", "--out")
    r.add_argument("--discover", action="store_true", help="also run the discovery stage (judge calls)")
    _judge_args(r)
    r.set_defaults(fn=cmd_run)
    dc = sub.add_parser("discover", help="find and verify open-ended effects in an existing bundle (judge calls only)")
    dc.add_argument("bundle")
    dc.add_argument("-o", "--out")
    _judge_args(dc)
    dc.set_defaults(fn=cmd_discover)
    pl = sub.add_parser("plan", help="count the answers and discovery calls a run spec would make (no model calls)")
    pl.add_argument("spec")
    for flag in ("--max-discovered", "--max-intended", "--proposal-calls", "--rejudge-per-class"):
        pl.add_argument(flag, type=int)
    pl.set_defaults(fn=cmd_plan)
    cf = sub.add_parser("confirm", help="retest screen candidates, chosen by a fixed rule, on fresh questions")
    cf.add_argument("bundle", help="a finished bundle with a discovery block (the screen)")
    cf.add_argument("spec", help="YAML with the fresh questions, seed, sample counts and provider")
    cf.add_argument("-o", "--out", required=True)
    cf.add_argument("--plan", action="store_true", help="print the candidates and the plan, make no model calls")
    cf.add_argument("--max-answers", type=int, help="refuse to run if the plan needs more answers")
    cf.add_argument("--max-judge-calls", type=int, help="refuse to run if judge plus re-judge calls may exceed this")
    cf.add_argument("--judge-base-url")
    cf.add_argument("--judge-model")
    cf.add_argument("--stub-judge", action="store_true")
    cf.add_argument("--keep-failed-calls", action="store_true",
                    help="write the result even if judge calls failed (they count as unreadable, as in discovery). "
                         "Only for calls that failed on two identical reruns; see docs/discovery.md")
    cf.set_defaults(fn=cmd_confirm)
    ro = sub.add_parser("readout", help="per-statement facts and per-part readings from a finished bundle (no model calls)")
    ro.add_argument("bundle", help="a bundle with a discovery block, with or without a confirmation")
    ro.add_argument("-o", "--out", required=True)
    ro.add_argument("--audit", help="audit YAML: statements marked `valid: false` are left out of the reading")
    ro.add_argument("--annotations", help="annotations YAML: author notes and label overrides per check, and a run description")
    ro.set_defaults(fn=cmd_readout)
    au = sub.add_parser("authored", help="judge author-written statements on a finished bundle's stored answers")
    au.add_argument("bundle", help="a finished bundle with a discovery block (its judge settings must be matched)")
    au.add_argument("statements", help="YAML of pre-registered statements (see docs/discovery.md)")
    au.add_argument("-o", "--out", required=True)
    au.add_argument("--plan", action="store_true", help="print the plan, make no model calls")
    au.add_argument("--max-judge-calls", type=int, help="refuse to run if judge plus re-judge calls may exceed this")
    au.add_argument("--judge-base-url")
    au.add_argument("--judge-model")
    au.add_argument("--stub-judge", action="store_true")
    au.add_argument("--keep-failed-calls", action="store_true",
                    help="write the result even if some judge calls failed (they count as unreadable)")
    au.set_defaults(fn=cmd_authored)

    lb = sub.add_parser("label", help="write a short label for each statement the readout uses (one judge call each)")
    lb.add_argument("bundle", help="a bundle with a readout")
    lb.add_argument("-o", "--out", required=True)
    lb.add_argument("--force", action="store_true", help="relabel statements that already have a label")
    lb.add_argument("--max-calls", type=int, help="make at most this many label calls; the rest keep no label")
    lb.add_argument("--judge-base-url")
    lb.add_argument("--judge-model")
    lb.add_argument("--stub-judge", action="store_true")
    lb.set_defaults(fn=cmd_label)

    v = sub.add_parser("validate", help="validate bundle files")
    v.add_argument("paths", nargs="+")
    v.set_defaults(fn=cmd_validate)
    rs = sub.add_parser("rescore", help="re-analyse a bundle's stored answers with the current detectors and statistics")
    rs.add_argument("bundle")
    rs.add_argument("-o", "--out")
    rs.set_defaults(fn=cmd_rescore)
    sv = sub.add_parser("serve", help="run the analysis API used by the web app")
    sv.add_argument("--runs-dir", default="web/public/runs")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)
    mk = sub.add_parser("mock", help="serve a fake OpenAI-compatible endpoint (stub model) for testing")
    mk.add_argument("--port", type=int, default=8001)
    mk.set_defaults(fn=cmd_mock)
    s = sub.add_parser("schema", help="print the bundle JSON Schema")
    s.set_defaults(fn=lambda a: print(bundle.json_schema(), end="") or 0)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
