import socket
import threading
import time

import pytest

fastapi = pytest.importorskip("fastapi")
uvicorn = pytest.importorskip("uvicorn")
from fastapi.testclient import TestClient  # noqa: E402

from spet.mock import create_mock  # noqa: E402
from spet.server import create_app  # noqa: E402
from spet.split import split_heuristic, validate_model_split  # noqa: E402

PROMPT = """You are the support assistant for Lumen, a developer tools company.

Always apologise when the user reports a problem, even if it is not our fault.

Be humble about uncertainty and avoid overstating what you know.

Use bullet points for any steps the user should follow."""


def test_heuristic_split_paragraphs_and_verbatim():
    secs = split_heuristic(PROMPT)
    assert len(secs) == 4
    assert all(s.text in PROMPT for s in secs)


def test_heuristic_split_xml_and_headings():
    xml = "<role>You are X and you help people.</role>\n<style>Be brief, kind, and very direct always.</style>\ntrailing note that matters here."
    assert [s.label for s in split_heuristic(xml)][:2] == ["Role", "Style"]
    md = "# Role\nYou are X and you help people with things.\n\n# Style\nBe brief and kind and direct in replies."
    assert [s.label for s in split_heuristic(md)] == ["Role", "Style"]


def test_model_split_rejects_paraphrase():
    good = '{"sections": [{"label": "Role", "text": "You are the support assistant for Lumen, a developer tools company."}, {"label": "Rest", "text": "Always apologise when the user reports a problem, even if it is not our fault.\\n\\nBe humble about uncertainty and avoid overstating what you know.\\n\\nUse bullet points for any steps the user should follow."}]}'
    assert validate_model_split(PROMPT, good)
    bad = good.replace("Always apologise", "Apologise often")
    assert validate_model_split(PROMPT, bad) is None


@pytest.fixture()
def mock_url():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    server = uvicorn.Server(uvicorn.Config(create_mock(latency=0), host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}/v1"
    server.should_exit = True
    t.join(timeout=5)


def test_full_flow_against_mock_endpoint(tmp_path, mock_url, monkeypatch):
    monkeypatch.chdir(tmp_path)  # provider cache goes here
    client = TestClient(create_app(tmp_path / "runs"))
    ep = {"base_url": mock_url, "model": "stub"}

    split = client.post("/api/split", json={"prompt": PROMPT, "use_model": True, "endpoint": ep}).json()
    assert split["method"] == "heuristic" and len(split["sections"]) == 4

    with client:
        r = client.post("/api/runs", json={"title": "Support prompt", "sections": split["sections"],
                                           "queries": ["My build fails.", "Export is empty.", "CI times out."],
                                           "n_per_query": 6, "endpoint": ep})
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        for _ in range(300):
            st = client.get(f"/api/runs/{rid}/status").json()
            if st["state"] != "running":
                break
            time.sleep(0.05)
        assert st["state"] == "done", st
        assert st["done"] == st["total"] == 5 * 3 * 6

    b = client.get(f"/api/runs/{rid}").json()
    sig = {(e["detector"], e["section"]) for e in b["effects"] if e["significant"]}
    assert ("apology", 1) in sig and ("hedge", 2) in sig and ("list_item", 3) in sig
    assert not any(k == 0 for _, k in sig)
    assert client.get("/api/runs").json()["runs"][0]["id"] == rid


def test_run_without_endpoint_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.delenv("SPET_BASE_URL", raising=False)
    client = TestClient(create_app(tmp_path / "runs"))
    r = client.post("/api/runs", json={"sections": [{"label": "a", "text": "b"}]})
    assert r.status_code == 400 and "SPET_BASE_URL" in r.json()["detail"]
