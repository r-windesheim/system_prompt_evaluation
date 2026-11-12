from pathlib import Path

from spet import bundle
from spet.cli import main

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "stub-demo.yaml"


def test_run_then_validate(tmp_path):
    out = tmp_path / "b.json"
    assert main(["run", str(EXAMPLE), "-o", str(out)]) == 0
    assert main(["validate", str(out)]) == 0
    b = bundle.load(out)
    sig = {(e.detector, e.section) for e in b.effects if e.significant}
    # inert sections (0: context, 6: length limit) must carry no attribution
    assert not {k for _, k in sig} & {0, 6}
    assert ("apology", 1) in sig and ("list_item", 3) in sig


def test_rescore_refreshes_detector_version(tmp_path):
    from spet.run import rescore

    out = tmp_path / "b.json"
    assert main(["run", str(EXAMPLE), "-o", str(out)]) == 0
    b = bundle.load(out)
    b.meta.settings["detector_version"] = "stale"
    assert rescore(b).meta.settings["detector_version"] != "stale"
