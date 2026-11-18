"""spet CLI.

    python -m spet run examples/stub-demo.yaml -o web/public/runs/stub-demo.json
    python -m spet validate web/public/runs/*.json
    python -m spet schema > docs/run-bundle.schema.json
    python -m spet discover runs/x.json -o runs/x.json     # judge calls only, no new answers
    python -m spet plan examples/sonnet35-july2024.yaml    # planned answers and judge calls, no model calls
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
