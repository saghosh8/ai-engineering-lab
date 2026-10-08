import json

import pytest
from pydantic import ValidationError

from src.llm_client import LLMOutputError, diagnose, extract_json
from tests.conftest import FakeClient

FACTS = {"exit_code": 1, "restart_count": 6}
LOGS = "ERROR psycopg2.OperationalError: could not connect to server: Connection timed out"
GOOD = {
    "likely_cause": "Database unreachable",
    "evidence": ["psycopg2.OperationalError: could not connect to server", "exit_code: 1"],
    "confidence": "high",
    "recommended_next_step": "kubectl get svc db-primary",
}


def test_plain_json():
    d = diagnose(FACTS, LOGS, client=FakeClient(json.dumps(GOOD)))
    assert d.confidence == "high" and d.unverified_evidence == []


def test_fenced_and_chatty_json():
    text = "Sure!\n```json\n" + json.dumps(GOOD) + "\n```\nHope that helps."
    assert diagnose(FACTS, LOGS, client=FakeClient(text)).likely_cause == "Database unreachable"


def test_invented_evidence_is_flagged_not_dropped():
    bad = dict(GOOD, evidence=GOOD["evidence"] + ["FATAL out of memory: killed process 4312"])
    d = diagnose(FACTS, LOGS, client=FakeClient(json.dumps(bad)))
    assert len(d.evidence) == 3
    assert d.unverified_evidence == ["FATAL out of memory: killed process 4312"]


def test_model_cannot_pre_fill_unverified_field():
    sneaky = dict(GOOD, unverified_evidence=[], evidence=["totally made up zzz qqq"])
    d = diagnose(FACTS, LOGS, client=FakeClient(json.dumps(sneaky)))
    assert d.unverified_evidence == ["totally made up zzz qqq"]


def test_truncated_response_rejected():
    with pytest.raises(LLMOutputError, match="truncated"):
        diagnose(FACTS, LOGS, client=FakeClient('{"likely_cause": "x', stop_reason="max_tokens"))


@pytest.mark.parametrize("text", ["I cannot help with that.", ""])
def test_no_json_rejected(text):
    with pytest.raises(LLMOutputError):
        diagnose(FACTS, LOGS, client=FakeClient(text))


def test_wrong_schema_rejected():
    with pytest.raises(ValidationError):
        diagnose(FACTS, LOGS, client=FakeClient('{"likely_cause": "x"}'))


def test_extract_json_outermost_object():
    assert json.loads(extract_json('pre {"a": {"b": 1}} post')) == {"a": {"b": 1}}
