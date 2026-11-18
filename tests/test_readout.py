"""Readout: two facts per intended statement and one reading per part, from stored data only (stub runs)."""

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from spet import bundle as B
from spet import readout as R
from spet.bundle import Check
from spet.cli import main
from spet.discovery import discover
from spet.providers import StubProvider
from spet.run import rescore
from spet.stub import respond
from test_confirm import _confirm, _screen, _spec
from test_discovery import _trun

ROOT = Path(__file__).resolve().parents[1]


def _c(does, cause="not_shown"):
    return Check(id="x", text="x", data="screen", rate_with=0.5, rate_without=0.5, n_questions=1, n_answers=1,
                 does=does, cause=cause)


# ---- question 1 and question 2, per statement -------------------------------------------------------------

@pytest.mark.parametrize("rate,ci,want", [
    (0.9, (0.85, 1.0), "mostly"), (0.8, (0.7, 0.9), "mostly"),        # 0.8 itself is mostly
    (0.1, (0.0, 0.15), "rarely"), (0.2, (0.1, 0.3), "rarely"),        # 0.2 itself is rarely
    (0.5, (0.3, 0.7), "sometimes"), (0.79, (0.6, 0.9), "sometimes"),
    (0.5, (0.2, 0.8), "unclear"), (0.9, (0.1, 1.0), "unclear"),      # the interval reaches both bounds
    (0.0, (0.0, 0.0), "rarely"), (1.0, (1.0, 1.0), "mostly"),        # never seen / ceiling: still an estimate
    (0.85, None, "mostly"),
])
def test_does(rate, ci, want):
    assert R.does(rate, ci) == want


def test_cause():
    assert R.cause(True, 0.95, 0.9) == "confirmed"  # confirmed wins over not needed
    assert R.cause(False, 0.95, 0.8) == "not_needed"
    assert R.cause(False, 0.95, 0.79) == "not_shown"
    assert R.cause(False, 0.1, 0.1) == "not_shown"


@pytest.mark.parametrize("checks,want", [
    ([], "unclear"),
    ([("unclear",), ("unclear",)], "unclear"),
    ([("mostly", "confirmed"), ("mostly", "not_needed"), ("mostly", "not_shown")], "followed"),
    ([("mostly", "not_needed"), ("mostly", "not_needed")], "not_needed"),
    ([("mostly", "not_needed"), ("mostly", "not_shown")], "does_it"),
    ([("mostly", "not_shown")], "does_it"),
    ([("rarely",), ("rarely",)], "not_followed"),
    ([("mostly", "confirmed"), ("rarely",)], "partly_followed"),
    ([("sometimes",), ("sometimes",)], "partly_followed"),
    ([("mostly", "confirmed"), ("unclear",)], "partly_followed"),  # an unclear check is not dropped
    ([("rarely",), ("unclear",)], "partly_followed"),
])
def test_part_reading(checks, want):
    assert R.part_reading([_c(*c) for c in checks]) == want


# ---- on bundles ---------------------------------------------------------------------------------------------

def _with(parts):
    """The targeted stub screen, with part k's intended statements replaced by one per (full, ablated, ci, flags)
    in ``parts[k]``, ids p<k>.i0, p<k>.i1, ... (copies of its first intended statement)."""
    _, d = _trun()
    raw = json.loads(d.model_dump_json())
    sts = raw["discovery"]["statements"]
    for k, rows in parts.items():
        proto = next(s for s in sts if s["section"] == k and s["source"] == "intended")
        sts[:] = [s for s in sts if not (s["section"] == k and s["source"] == "intended")]
        for i, (full, abl, ci, flags) in enumerate(rows):
            sts.append({**proto, "id": f"p{k}.i{i}", "full_rate": full, "ablated_rate": abl, "full_rate_ci": list(ci),
                        "flags": list(flags), "examples": [], "verdicts": [], "rejudged": []})
    for r in raw["discovery"]["readings"]:
        r["confirmed"] = []
    return B.RunBundle.model_validate(raw)


def test_flags_and_audit_decide_what_is_used():
    b = _with({
        2: [(0.0, 0.0, (0.0, 0.0), ["never_seen", "rejudge_one_class"]),  # kept: a never-seen behaviour
            (0.05, 0.0, (0.0, 0.1), ["judge_unreliable"]), (0.05, 0.0, (0.0, 0.1), ["exclusion_asymmetry"])],
        0: [(1.0, 1.0, (1.0, 1.0), ["ceiling"]), (0.95, 0.9, (0.9, 1.0), []),
            (0.1, 0.1, (0.0, 0.2), ["few_pairs"]), (0.1, 0.1, (0.0, 0.2), ["unparseable"])],
    })
    out = R.readout(b)
    parts = {p.section: p for p in out.readout.parts}
    p2, p0 = parts[2], parts[0]
    assert [c.id for c in p2.checks] == ["p2.i0"] and p2.reading == "not_followed"
    assert p2.checks[0].does == "rarely" and R.ONE_CLASS_NOTE in p2.checks[0].note and R.ONE_CLASS_NOTE in p2.note
    assert [e.reason for e in p2.excluded] == ["flag in the main run: judge_unreliable",
                                                "flag in the main run: exclusion_asymmetry"]
    assert [c.id for c in p0.checks] == ["p0.i0", "p0.i1"]
    assert p0.reading == "not_needed" and all(c.cause == "not_needed" for c in p0.checks)
    assert [e.reason for e in p0.excluded] == ["flag in the main run: few_pairs", "flag in the main run: unparseable"]
    assert out.readout.audit is None and out.schema_version == B.SCHEMA_VERSION == 9

    # an audit leaves invalid statements out, with its reason; a part with nothing left reads unclear
    ids = [s.id for s in b.discovery.statements if s.source == "intended"]
    audit = {i: (not i.startswith("p0."), "not checkable") for i in ids}
    out = R.readout(b, audit)
    p0 = next(p for p in out.readout.parts if p.section == 0)
    assert p0.reading == "unclear" and not p0.checks and p0.note.startswith("No usable check")
    assert {e.reason for e in p0.excluded} == {"audit: not checkable"}


def test_does_it_and_partly_followed_on_a_bundle():
    b = _with({0: [(0.9, 0.3, (0.8, 1.0), []), (0.85, 0.85, (0.8, 0.9), [])],
               2: [(0.9, 0.3, (0.8, 1.0), []), (0.5, 0.5, (0.3, 0.7), [])]})
    parts = {p.section: p for p in R.readout(b).readout.parts}
    assert parts[0].reading == "does_it" and [c.cause for c in parts[0].checks] == ["not_shown", "not_needed"]
    assert parts[2].reading == "partly_followed" and [c.does for c in parts[2].checks] == ["mostly", "sometimes"]


def test_confirmation_data_takes_precedence(tmp_path):
    b = _screen()
    out = _confirm(b, _spec(tmp_path))
    cand = {c.id: c for c in out.confirmation.candidates}
    ro = R.readout(out)
    checks = {c.id: c for p in ro.readout.parts for c in p.checks}
    c1, s1 = checks["p1.i0"], cand["p1.i0"]
    assert c1.data == "confirmation" and c1.rate_with == s1.full_rate and c1.n_answers == s1.n_pairs
    assert c1.rate_with_ci == s1.full_rate_ci and c1.n_questions == s1.n_questions and c1.cause == "confirmed"
    screen = next(s for s in out.discovery.statements if s.id == "p1.i0")
    assert (screen.full_rate, screen.n_pairs) != (s1.full_rate, s1.n_pairs)  # the two runs really differ
    # discovered candidates never enter the reading; statements not retested use the main run
    assert "p3.d0" not in checks and all(c.data == "screen" for i, c in checks.items() if i not in cand)
    p1 = next(p for p in ro.readout.parts if p.section == 1)
    assert p1.adherence == "followed" and p1.adherence_basis == "confirmation"

    # the confirmation's flags count, not the screen's: a candidate unreliable there is left out, not read
    raw = json.loads(out.model_dump_json())
    next(c for c in raw["confirmation"]["candidates"] if c["id"] == "p1.i0")["flags"].append("judge_unreliable")
    ro2 = R.readout(B.RunBundle.model_validate(raw))
    p1 = next(p for p in ro2.readout.parts if p.section == 1)
    assert "p1.i0" not in {c.id for c in p1.checks}
    assert next(e for e in p1.excluded if e.id == "p1.i0").reason == "flag in the confirmation run: judge_unreliable"


def test_old_bundles_and_lifecycle(tmp_path):
    _, d = _trun()
    raw = json.loads(d.model_dump_json())
    raw.update(schema_version=6)
    old = B.RunBundle.model_validate(raw)  # a v6 bundle without a readout loads
    assert old.readout is None
    out = R.readout(old)  # a screen without confirmation is read too
    assert out.schema_version == 9 and len(out.readout.parts) == len(old.sections)
    assert all(c.data == "screen" and c.cause != "confirmed" for p in out.readout.parts for c in p.checks)
    p = tmp_path / "r.json"
    B.dump(out, p)
    assert B.load(p) == out
    assert rescore(out).readout == out.readout
    assert asyncio.run(discover(out, StubProvider(respond, model="stub-judge"))).readout is None
    raw.update(discovery=None, confirmation=None)
    with pytest.raises(ValueError):
        R.readout(B.RunBundle.model_validate(raw))
    bad = json.loads(out.model_dump_json())
    bad["readout"]["parts"][1]["checks"][0]["id"] = "p9.i9"
    with pytest.raises(Exception):
        B.RunBundle.model_validate(bad)


def test_cli_readout_with_audit(tmp_path):
    _, d = _trun()
    src, dst, a = tmp_path / "b.json", tmp_path / "o.json", tmp_path / "a.yaml"
    B.dump(d, src)
    ids = [s.id for s in d.discovery.statements if s.source == "intended"]
    entries = {i: {"valid": i != ids[0], "reason": "dangling referent"} for i in ids}
    a.write_text(yaml.safe_dump({"reviewer": "r", "date": "2026-01-01", "statements": entries}))
    assert main(["readout", str(src), "-o", str(dst), "--audit", str(a)]) == 0
    out = B.load(dst)
    assert out.readout.audit.invalid == [ids[0]] and len(out.readout.audit.sha256) == 64
    assert any(e.id == ids[0] for p in out.readout.parts for e in p.excluded)
    assert main(["validate", str(dst)]) == 0
    a.write_text(yaml.safe_dump({"statements": {i: entries[i] for i in ids[1:]}}))
    with pytest.raises(SystemExit, match="no audit entry"):
        main(["readout", str(src), "-o", str(dst), "--audit", str(a)])


V4 = ROOT / "runs_out" / "sonnet35-july2024-v4.json"
AUDIT = ROOT / "examples" / "sonnet35-july2024-audit.yaml"


@pytest.mark.skipif(not V4.exists(), reason="needs the July 2024 readout")
def test_july_2024_readout_matches_the_audit():
    b = B.load(V4)
    a = yaml.safe_load(AUDIT.read_text())["statements"]
    assert b.readout.audit.valid == sorted(i for i, e in a.items() if e["valid"])
    used = {c.id for p in b.readout.parts for c in p.checks}
    assert used <= set(b.readout.audit.valid) and len(b.readout.parts) == 16
