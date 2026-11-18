"""Build index.html from template.html + the Lumen run bundle.

Run from anywhere: python3 docs/prototypes/minimal/build.py
Extracts only what the mockup needs (parts, notable effects, one example pair per part).
"""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[2]
run = json.loads((root / "web/public/runs/lumen-original-probes.json").read_text())

R = {(r["config"], r["query_idx"], r["sample_idx"]): r for r in run["responses"]}
det = {d["id"]: d for d in run["detectors"]}

# Hand-picked example pairs (query_idx, sample_idx) and which spans to highlight in them.
PAIRS = {
    0: (1, 0, []),
    1: (2, 5, ["sympathy"]),
    2: (0, 6, []),
    3: (2, 4, ["list_item"]),
    4: (0, 5, []),
    5: (1, 2, ["exclamation"]),
}


def answer(cfg, q, s, highlight):
    r = R[(cfg, q, s)]
    spans = [[sp["start"], sp["end"]] for sp in r["spans"] if sp["detector"] in highlight]
    return {"text": r["text"].strip(), "spans": spans, "words": len(r["text"].split())}


parts = []
for sec in run["sections"]:
    i = sec["id"]
    eff = [e for e in run["effects"] if e["section"] == i]
    sig = sorted([e for e in eff if e["significant"]], key=lambda e: e["q"])
    tested = [e for e in eff if e["tested"]]
    p = {
        "id": i,
        "label": sec["label"],
        "text": sec["text"],
        "notes": sec.get("notes", []),
        "tested": len(tested),
        "effects": [
            {k: e[k] for k in ("detector", "full_mean", "ablated_mean", "delta", "ci", "q", "flags", "n_pairs")}
            | {"kind": det[e["detector"]].get("kind", "habit")}
            for e in sig
        ],
        "untestable": [e["detector"] for e in eff if not e["tested"]],
        "extra": {},
    }
    # Values used in plain-language caveats.
    for e in eff:
        if e["detector"] in ("apology", "ends_question"):
            p["extra"][e["detector"]] = {k: e[k] for k in ("full_mean", "ablated_mean", "q", "tested")}
    if i in PAIRS:
        q, s, hl = PAIRS[i]
        p["pair"] = {
            "question": run["meta"]["queries"][q],
            "with": answer("full", q, s, hl),
            "without": answer(f"without_{i}", q, s, hl),
        }
    parts.append(p)

data = {
    "model": run["meta"]["model"].split("/")[-1],
    "queries": run["meta"]["queries"],
    "n": run["meta"]["n_per_query"],
    "longest": max(len(r["text"].split()) for r in run["responses"]),
    "warnings": run["analysis"]["warnings"],
    "parts": parts,
}

html = (here / "template.html").read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
(here / "index.html").write_text(html)
print("wrote", here / "index.html", len(html), "bytes")
