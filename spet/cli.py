"""spet CLI.

    python -m spet run examples/stub-demo.yaml -o web/public/runs/stub-demo.json
    python -m spet validate web/public/runs/*.json
    python -m spet schema > docs/run-bundle.schema.json
"""

from __future__ import annotations

import argparse
import asyncio
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


def load_spec(path: Path) -> tuple[RunSpec, dict]:
    raw = yaml.safe_load(path.read_text())
    secs = raw["sections"]
    spec = RunSpec(
        id=raw.get("id", path.stem),
        title=raw.get("title", path.stem),
        sections=[s["text"] if isinstance(s, dict) else s for s in secs],
        section_labels=[s.get("label", f"Section {i + 1}") if isinstance(s, dict) else f"Section {i + 1}"
                        for i, s in enumerate(secs)],
        queries=raw.get("queries") or DEFAULT_QUERIES,
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
    out = Path(args.out or f"{spec.id}.json")
    bundle.dump(b, out)
    sig = [e for e in b.effects if e.significant]
    print(f"wrote {out}: {len(b.responses)} responses, {len(sig)} significant effects", file=sys.stderr)
    for e in sorted(sig, key=lambda e: e.q)[:10]:
        print(f"  {e.detector:<14} section {e.section}  delta {e.delta:+.2f}  "
              f"CI [{e.ci[0]:+.2f}, {e.ci[1]:+.2f}]  q={e.q:.3g}", file=sys.stderr)
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spet")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="execute a run spec and write a bundle")
    r.add_argument("spec")
    r.add_argument("-o", "--out")
    r.set_defaults(fn=cmd_run)
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
