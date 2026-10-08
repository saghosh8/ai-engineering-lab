import json

from src import troubleshooter
from tests.conftest import FakeClient
from tests.test_llm_client import GOOD


def test_llm_failure_falls_back_to_raw_evidence(monkeypatch):
    monkeypatch.setattr("src.llm_client.Anthropic", lambda: FakeClient("not json"))
    r = troubleshooter.investigate_from_data({"exit_code": 1}, "token=abcdef123456 boom")
    assert not r.succeeded and r.error
    assert "abcdef123456" not in r.log_excerpt  # redaction still applied on fallback


def test_happy_path(monkeypatch):
    monkeypatch.setattr("src.llm_client.Anthropic", lambda: FakeClient(json.dumps(GOOD)))
    r = troubleshooter.investigate_from_data({"exit_code": 1}, "exit_code: 1")
    assert r.succeeded
