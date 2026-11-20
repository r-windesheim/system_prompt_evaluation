"""Labels (schema 9): the rules, the same-call format, `spet label`, and the readout's author notes. Stub runs only."""

import asyncio
import json

import pytest
import yaml

from spet import bundle as B
from spet import label as L
from spet import prompts as P
from spet import readout as R
from spet.cli import main
from spet.providers import StubProvider
from spet.stub import respond
from test_discovery import _trun


@pytest.mark.parametrize("label,ok", [
    ("says it cannot open the link", True),
    ("does not start with an apology", True),
    ("doesn't apologise", True),
    ("is willing to help", True),
    ("keeps simple answers within sixty words", True),
    ("the answer is short", False),                       # not a verb, and "the answer"
    ("says the answer is short", False),                  # "the answer"
    ("answer is short", False),                           # not a verb form
    ("its tone is warm", False),
    ("ends with a long follow-up question about what the user tried", False),  # over eight words
    ('says "I cannot open links or videos ever"', False),  # quotes more than five words
    ('says "I cannot open links"', True),
    ("", False),
])
def test_label_rules(label, ok):
    assert (P.label_problem(label) is None) is ok


def test_clean_label():
    assert P.clean_label("The model says it cannot open links.") == "says it cannot open links"
    assert P.clean_label("Label: Says hello") == "says hello"
    assert P.clean_label("thinking...\n- asks a question") == "asks a question"


def test_same_call_labels_are_parsed_and_checked():
    out = P.parse_labelled("- The answer says it cannot open links. || says it cannot open links\n"
                           "- The answer is short. || the answer is short\n"
                           "- The answer ends with a question.\n"
                           "- Answer A is longer than answer B. || is longer", 5)
    assert out == [("The answer says it cannot open links.", "says it cannot open links"),
                   ("The answer is short.", None),               # a label that breaks the rules is dropped
                   ("The answer ends with a question.", None)]  # no label given
    assert P.parse_statements("- The answer is short. || is short", 5) == ["The answer is short."]


def test_versions():
    # labels changed only the proposer prompts: bundles recorded before them still match the judge check
    assert P.version() != P.version_before_labels() == "aa7f27472e6b"
    assert len(P.judge_version()) == 12 and "|| " in P.INTENDED_SYSTEM and "|| " in P.PROPOSE_SYSTEM


def _readout_bundle():
    _, d = _trun()
    return R.readout(d)


def test_label_bundle_with_the_stub_judge():
    b = _readout_bundle()
    ids = L.targets(b)
    assert ids
    out, rep = asyncio.run(L.label_bundle(b, StubProvider(respond, model="stub-judge")))
    checks = {c.id: c for p in out.readout.parts for c in p.checks}
    sts = {s.id: s for s in out.discovery.statements}
    for sid in ids:
        lab = rep["labels"][sid]
        assert sts[sid].label == lab == checks[sid].label
        assert lab is None or P.label_problem(lab) is None
    # the stub's conditional statement ("If the answer contains code, ...") gives a bad label twice: no label
    bad = [sid for sid in ids if sts[sid].text.startswith("If ")]
    assert all(rep["labels"][sid] is None and sid in rep["failed"] for sid in bad)
    assert rep["calls"] == len(ids) + len(rep["failed"])  # one retry per failure
    assert out.schema_version == B.SCHEMA_VERSION == 9 and out.meta.settings["label_prompts_version"]
    # a rebuilt readout keeps the labels; labels never change a reading
    again = R.readout(out)
    assert {c.id: c.label for p in again.readout.parts for c in p.checks} == {i: c.label for i, c in checks.items()}
    assert [p.reading for p in again.readout.parts] == [p.reading for p in b.readout.parts]


def test_label_budget_and_force():
    b = _readout_bundle()
    out, rep = asyncio.run(L.label_bundle(b, StubProvider(respond, model="stub-judge"), max_calls=2))
    assert rep["calls"] == 2 and rep["skipped"]
    out2, rep2 = asyncio.run(L.label_bundle(out, StubProvider(respond, model="stub-judge")))
    # a second pass asks only for what is still unlabelled: the skipped ones, and any whose label failed the rules
    assert set(rep2["labels"]) == set(rep["skipped"]) | set(rep["failed"])
    _, rep3 = asyncio.run(L.label_bundle(out2, StubProvider(respond, model="stub-judge"), force=True))
    assert set(rep3["labels"]) == set(L.targets(b))


def test_annotations_and_cli(tmp_path):
    _, d = _trun()
    src, lab, dst, notes = tmp_path / "b.json", tmp_path / "l.json", tmp_path / "o.json", tmp_path / "n.yaml"
    B.dump(R.readout(d), src)
    assert main(["label", str(src), "-o", str(lab), "--stub-judge"]) == 0
    sid = next(c.id for p in B.load(lab).readout.parts for c in p.checks)
    notes.write_text(yaml.safe_dump({"author": "a", "date": "2026-01-01", "notes": {sid: "  A short   note. "}}))
    assert main(["readout", str(lab), "-o", str(dst), "--annotations", str(notes)]) == 0
    out = B.load(dst)
    c = next(c for p in out.readout.parts for c in p.checks if c.id == sid)
    assert c.author_note == "A short note."
    assert out.readout.annotations.file == "n.yaml" and len(out.readout.annotations.sha256) == 64
    assert all(c.author_note is None for p in out.readout.parts for c in p.checks if c.id != sid)
    notes.write_text(yaml.safe_dump({"notes": {"p9.i9": "x"}}))
    with pytest.raises(SystemExit, match="not statements of this bundle"):
        main(["readout", str(lab), "-o", str(dst), "--annotations", str(notes)])


def test_annotations_labels_and_description(tmp_path):
    _, d = _trun()
    src, dst, notes = tmp_path / "b.json", tmp_path / "o.json", tmp_path / "n.yaml"
    b = R.readout(d)
    B.dump(b, src)
    ids = [c.id for p in b.readout.parts for c in p.checks]
    sid = ids[0]
    desc = "A  prompt tested on a stand-in model."
    notes.write_text(yaml.safe_dump({"author": "a", "description": desc,
                                     "labels": {sid: "  says   what the author wrote"}}))
    assert main(["readout", str(src), "-o", str(dst), "--annotations", str(notes)]) == 0
    out = B.load(dst)
    checks = {c.id: c for p in out.readout.parts for c in p.checks}
    assert checks[sid].label == "says what the author wrote" and checks[sid].label_source == "author"
    assert all(c.label_source is None for k, c in checks.items() if k != sid)
    assert all(c.author_note is None for c in checks.values())
    rec = out.readout.annotations
    assert rec.labels == {sid: "says what the author wrote"}
    assert rec.description == "A prompt tested on a stand-in model."
    # the statement keeps its own label; only the check shows the author's
    st = {s.id: s for s in out.discovery.statements}
    assert st[sid].label == {s.id: s for s in b.discovery.statements}[sid].label
    # the rest of the readout is the same as without annotations
    plain = {c.id: c for p in b.readout.parts for c in p.checks}
    for k, c in checks.items():
        assert (c.rate_with, c.does, c.cause, c.text) == (plain[k].rate_with, plain[k].does, plain[k].cause, plain[k].text)
        if k != sid:
            assert c.label == plain[k].label


@pytest.mark.parametrize("raw, match", [
    ({"labels": {"p9.i9": "says x"}}, "not statements of this bundle"),
    ({"labels": {"SID": "the answer is short"}}, "breaks the label rules"),
    ({"labels": {"SID": "says one two three four five six seven eight"}}, "breaks the label rules"),
    ({"labels": ["says x"]}, "`labels` must map"),
    ({"description": "   "}, "description must be"),
    ({"description": "x" * 301}, "description must be"),
])
def test_annotations_rejects(tmp_path, raw, match):
    _, d = _trun()
    b = R.readout(d)
    sid = next(c.id for p in b.readout.parts for c in p.checks)
    raw = json.loads(json.dumps(raw).replace("SID", sid))
    f = tmp_path / "n.yaml"
    f.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match=match):
        R.load_annotations(f, b)


def test_annotations_without_labels_or_description(tmp_path):
    _, d = _trun()
    b = R.readout(d)
    f = tmp_path / "n.yaml"
    f.write_text(yaml.safe_dump({"author": "a"}))
    notes, rec = R.load_annotations(f, b)
    assert notes == {} and rec.labels == {} and rec.description is None
    out = R.readout(b, annotations=notes, annotations_record=rec)
    assert all(c.label_source is None for p in out.readout.parts for c in p.checks)


def test_v8_bundles_load_without_labels():
    b = _readout_bundle()
    raw = json.loads(b.model_dump_json())
    raw["schema_version"] = 8
    for s in raw["discovery"]["statements"]:
        s.pop("label", None)
    for p in raw["readout"]["parts"]:
        for c in p["checks"]:
            c.pop("label", None)
            c.pop("author_note", None)
    raw["readout"].pop("annotations", None)
    old = B.RunBundle.model_validate(raw)
    assert old.schema_version == 8 and all(s.label is None for s in old.discovery.statements)


def test_v9_bundles_load_without_label_source_or_description():
    b = _readout_bundle()
    raw = json.loads(b.model_dump_json())
    for p in raw["readout"]["parts"]:
        for c in p["checks"]:
            c.pop("label_source", None)
    raw["readout"]["annotations"] = {"file": "n.yaml", "sha256": "0" * 64, "author": "a", "date": "2026-11-18"}
    old = B.RunBundle.model_validate(raw)
    assert old.readout.annotations.labels == {} and old.readout.annotations.description is None
    assert all(c.label_source is None for p in old.readout.parts for c in p.checks)


def test_authored_file_label(tmp_path):
    from spet import authored as A
    _, d = _trun()
    part = next(s for s in d.sections if any(c.removed == s.id for c in d.configs))
    f = tmp_path / "s.yaml"
    f.write_text(yaml.safe_dump({"reviewer": "r", "date": "d", "statements": [
        {"id": "x.a0", "section": part.id, "text": "The answer apologises.", "label": "The model apologises."}]}))
    assert A.load(f, d).items[0].label == "apologises"
    f.write_text(yaml.safe_dump({"reviewer": "r", "date": "d", "statements": [
        {"id": "x.a0", "section": part.id, "text": "The answer apologises.", "label": "the answer apologises"}]}))
    with pytest.raises(ValueError, match="label"):
        A.load(f, d)


def test_example_annotations_match_the_committed_run():
    """The example's annotations file names statements of the committed run, and its labels follow the rules."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    run = root / "web" / "public" / "runs" / "sonnet35-july2024.json"
    b = B.load(run)
    notes, rec = R.load_annotations(root / "examples" / "sonnet35-july2024-annotations.yaml", b)
    assert set(rec.labels) == {"p4.i2", "p8.i1", "p12.a0", "p12.a1", "p13.i0", "p15.i0"}
    assert rec.description and "gpt-oss-20b" in rec.description
    shown = {c.id: c for p in b.readout.parts for c in p.checks}
    assert all(shown[k].label == v and shown[k].label_source == "author" for k, v in rec.labels.items())
