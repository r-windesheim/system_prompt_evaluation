"""Build the results-view mockups page from a real run bundle.

    venv/bin/python docs/mockups/build.py web/public/runs/<id>.json
    -> docs/mockups/index.html (self-contained, data inlined)
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
b = json.loads(Path(sys.argv[1]).read_text())

det_ids = [d["id"] for d in b["detectors"]]
data = {
    "title": b["meta"]["title"],
    "model": b["meta"]["model"],
    "n": b["meta"]["n_per_query"],
    "queries": b["meta"]["queries"],
    "sections": [{"id": s["id"], "label": s["label"], "text": s["text"]} for s in b["sections"]],
    "detectors": [{"id": d["id"], "label": d["label"], "group": d["group"], "description": d["description"]}
                  for d in b["detectors"]],
    "effects": [{k: e[k] for k in ("detector", "section", "full_mean", "ablated_mean", "delta", "ci", "q", "significant", "n_pairs")}
                for e in b["effects"]],
    # responses keyed "config|q|s" -> [text, [[start, end, detector_index], ...]]
    "responses": {f'{r["config"]}|{r["query_idx"]}|{r["sample_idx"]}':
                  [r["text"], [[sp["start"], sp["end"], det_ids.index(sp["detector"])] for sp in r["spans"]]]
                  for r in b["responses"]},
}
html = (HERE / "template.html").read_text().replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
(HERE / "index.html").write_text(html)
print(f"wrote {HERE / 'index.html'} ({len(html) // 1024} KB)")
