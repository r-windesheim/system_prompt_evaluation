"""Author-written statements: judged on a finished bundle's stored answers, read by the readout. Stub model and judge."""

import asyncio
import json
import os

import pytest
import yaml

from spet import authored as A
from spet import bundle as B
from spet import confirm as C
from spet import detectors
from spet import readout as R
from spet.cli import main
from spet.discovery import discover
from spet.providers import StubProvider
from spet.run import rescore
from spet.stub import respond
from test_discovery import _trun

CODE_OFFER = "If the answer contains code, it asks whether the user wants it to explain the code."
APOLOGY = "The answer apologises to the user."
SHORT = "The answer has at most 40 words."
CODE_QS = list(range(10))


@pytest.fixture(autouse=True)
def _no_real_endpoints(monkeypatch):
    for k in list(os.environ):
        if k.startswith("SPET_"):
            monkeypatch.delenv(k)


@pytest.fixture(scope="module")
def screen():
    return _trun()[1]


def _file(tmp_path, rows=None, name="a.yaml"):
    rows = rows if rows is not None else [
        {"id": "p1.a0", "section": 1, "text": CODE_OFFER, "polarity": "positive"},
        {"id": "p3.a0", "section": 3, "text": APOLOGY, "polarity": "reverse"},
        {"id": "p1.a1", "section": 1, "text": SHORT, "measure": {"metric": "words", "max": 40}, "queries": CODE_QS[:6]},
    ]
    p = tmp_path / name
    p.write_text(yaml.safe_dump({"reviewer": "r", "date": "2026-01-01", "statements": rows}))
    return p


def _judge(b, path, judge=None):
    return asyncio.run(A.judge_authored(b, A.load(path, b), judge or StubProvider(respond, model="stub-judge")))


def test_load_refuses_bad_files(screen, tmp_path):
    ok = {"id": "x.a0", "section": 1, "text": CODE_OFFER}
    for bad, msg in [
        ({**ok, "section": "No such part"}, "not a part"), ({**ok, "section": 0, "id": "p1.i0"}, "already"),
        ({**ok, "polarity": "negative"}, "polarity"), ({**ok, "measure": {"metric": "chars", "max": 3}}, "measure"),
        ({**ok, "measure": {"metric": "words"}}, "measure"), ({**ok, "queries": [10]}, "queries"),
        ({**ok, "text": " "}, "needs"),
    ]:
        with pytest.raises(ValueError, match=msg):
            A.load(_file(tmp_path, [bad]), screen)
    with pytest.raises(ValueError, match="duplicate"):
        A.load(_file(tmp_path, [ok, ok]), screen)
    s = A.load(_file(tmp_path, [ok]), screen)
    assert s.items[0].section == 1 and s.items[0].polarity == "positive" and len(s.sha256) == 64


def test_judged_like_discovery_but_outside_its_families(screen, tmp_path):
    out = _judge(screen, _file(tmp_path))
    a = out.authored
    st = {s.id: s for s in a.statements}
    # the same statement text as the stub's intended one, on the same cells: the same verdicts and rates
    ref = next(s for s in screen.discovery.statements if s.section == 1 and s.source == "intended")
    assert ref.text == CODE_OFFER
    s1 = st["p1.a0"]
    assert s1.verdicts == ref.verdicts and (s1.full_rate, s1.ablated_rate) == (ref.full_rate, ref.ablated_rate)
    assert s1.verified_on == CODE_QS and s1.n_pairs == ref.n_pairs and s1.n_rejudged > 0
    # estimates only: no family, no significance, q fixed at 1, p kept for information
    assert all(s.source == "authored" and s.family is None and not s.significant and s.q == 1.0 for s in a.statements)
    assert 0 <= s1.p <= 1 and out.discovery == screen.discovery and out.schema_version == B.SCHEMA_VERSION == 8
    assert C.select(out) == C.select(screen)  # never a confirmation candidate
    assert a.settings["judge_model"] == "stub-judge" and a.sha256 == A.load(_file(tmp_path), screen).sha256
    assert a.calls["judge"] == 2 * (s1.n_pairs + st["p3.a0"].n_pairs) and a.calls["rejudge"] <= 40


def test_measured_statement_uses_the_word_count_not_the_judge(screen, tmp_path):
    out = _judge(screen, _file(tmp_path))
    m = next(s for s in out.authored.statements if s.id == "p1.a1")
    texts = {(r.config, r.query_idx, r.sample_idx): r.text for r in screen.responses}
    for q, s, v in m.verdicts:
        assert v == "".join("y" if detectors.word_count(texts[(c, q, s)]) <= 40 else "n" for c in ("full", "without_1"))
    assert m.measure == "words <= 40" and m.verified_on == CODE_QS[:6] and {q for q, _, _ in m.verdicts} <= set(CODE_QS[:6])
    assert m.rejudged == [] and m.agreement is None and "judge_unchecked" not in m.flags


def test_readout_reads_reverse_statements_the_right_way_round(screen, tmp_path):
    out = _judge(screen, _file(tmp_path))
    raw_st = next(s for s in out.authored.statements if s.id == "p3.a0")
    ro = R.readout(out)
    checks = {c.id: c for p in ro.readout.parts for c in p.checks}
    c = checks["p3.a0"]
    assert c.data == "authored" and c.polarity == "reverse" and c.rate_with_raw == raw_st.full_rate
    assert c.rate_with == pytest.approx(1 - raw_st.full_rate) and c.rate_without == pytest.approx(1 - raw_st.ablated_rate)
    assert c.rate_with_ci == pytest.approx((1 - raw_st.full_rate_ci[1], 1 - raw_st.full_rate_ci[0]))
    assert R.REVERSE_NOTE in c.note and checks["p1.a0"].polarity == "positive"
    assert "Decided by the engine's words <= 40" in checks["p1.a1"].note
    # intended statements are still read, from the main run
    assert any(c.data == "screen" for c in checks.values())


@pytest.mark.parametrize("raw,ci,want", [(0.1, (0.0, 0.15), "mostly"), (0.9, (0.85, 1.0), "rarely"),
                                         (0.5, (0.2, 0.8), "unclear")])
def test_reverse_orientation(screen, raw, ci, want):
    st = B.Statement(id="p0.a0", section=0, text="t", source="authored", full_rate=raw, ablated_rate=0.05,
                     full_rate_ci=ci, delta=raw - 0.05, ci=(0, 0), p=1, q=1, significant=False, n_pairs=10,
                     n_questions=5, polarity="reverse")
    c = R._check(st, "authored", False)
    assert c.does == want and c.rate_with == pytest.approx(1 - raw) and c.rate_without == pytest.approx(0.95)
    assert c.cause == ("not_needed" if want == "mostly" else "not_shown")


def test_audit_must_cover_authored_statements(screen, tmp_path):
    out = _judge(screen, _file(tmp_path))
    src = tmp_path / "b.json"
    B.dump(out, src)
    ids = [s.id for s in out.discovery.statements if s.source == "intended"]
    base = {"reviewer": "r", "date": "d", "statements": {i: {"valid": True, "reason": ""} for i in ids}}
    a = tmp_path / "audit.yaml"
    a.write_text(yaml.safe_dump(base))
    with pytest.raises(SystemExit, match="no audit entry for authored"):
        main(["readout", str(src), "-o", str(tmp_path / "o.json"), "--audit", str(a)])
    auth = {"p1.a0": {"valid": True, "reason": ""}, "p3.a0": {"valid": False, "reason": "misjudged"},
            "p1.a1": {"valid": True, "reason": ""}}
    a.write_text(yaml.safe_dump({**base, "authored_statements": auth}))
    assert main(["readout", str(src), "-o", str(tmp_path / "o.json"), "--audit", str(a)]) == 0
    o = B.load(tmp_path / "o.json")
    p3 = next(p for p in o.readout.parts if p.section == 3)
    assert "p3.a0" not in {c.id for c in p3.checks}
    assert next(e for e in p3.excluded if e.id == "p3.a0").reason == "audit: misjudged"
    assert "p3.a0" in o.readout.audit.invalid
    a.write_text(yaml.safe_dump({**base, "authored_statements": {**auth, "p9.a9": {"valid": True}}}))
    with pytest.raises(SystemExit, match="not authored statements"):
        main(["readout", str(src), "-o", str(tmp_path / "o.json"), "--audit", str(a)])


def test_cli_plan_budget_run_and_lifecycle(screen, tmp_path, capsys):
    src, dst, f = tmp_path / "b.json", tmp_path / "o.json", _file(tmp_path)
    B.dump(screen, src)
    raw = json.loads(src.read_text())
    raw["meta"]["settings"]["judge_model"] = "stub-judge-v1"  # the judge the CLI makes for stub runs
    src.write_text(json.dumps(raw))
    assert main(["authored", str(src), str(f), "-o", str(dst), "--plan"]) == 0
    assert not dst.exists() and "plan: judge calls <=" in capsys.readouterr().err
    with pytest.raises(SystemExit, match="over budget"):
        main(["authored", str(src), str(f), "-o", str(dst), "--max-judge-calls", "5"])
    assert main(["authored", str(src), str(f), "-o", str(dst), "--max-judge-calls", "3000"]) == 0
    assert main(["validate", str(dst)]) == 0
    out = B.load(dst)
    assert [s.id for s in out.authored.statements] == ["p1.a0", "p3.a0", "p1.a1"]
    assert rescore(out).authored == out.authored
    assert asyncio.run(discover(out, StubProvider(respond, model="stub-judge"))).authored == out.authored
    # a judge that is not the screen's is refused
    raw["meta"]["settings"]["judge_max_tokens"] = 123
    src.write_text(json.dumps(raw))
    with pytest.raises(SystemExit, match="judge differs"):
        main(["authored", str(src), str(f), "-o", str(dst), "--plan"])


def test_old_bundles_load_and_bad_blocks_are_refused(screen, tmp_path):
    raw = json.loads(screen.model_dump_json())
    raw.update(schema_version=7)
    assert B.RunBundle.model_validate(raw).authored is None
    out = json.loads(_judge(screen, _file(tmp_path)).model_dump_json())
    bad = json.loads(json.dumps(out))
    bad["authored"]["statements"][0]["significant"] = True
    with pytest.raises(Exception):
        B.RunBundle.model_validate(bad)
    bad = json.loads(json.dumps(out))
    bad["authored"]["statements"][0]["id"] = "p1.i0"  # collides with a discovery statement
    with pytest.raises(Exception):
        B.RunBundle.model_validate(bad)
    ro = json.loads(R.readout(B.RunBundle.model_validate(out)).model_dump_json())
    ch = next(c for p in ro["readout"]["parts"] for c in p["checks"] if c["id"] == "p1.a0")
    ch["data"] = "screen"
    with pytest.raises(Exception):
        B.RunBundle.model_validate(ro)
