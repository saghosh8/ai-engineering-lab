import json
from pathlib import Path

import pytest

from src.analyzer import AnalysisError, call_llm, verify_evidence_grounding
from tests.conftest import FakeClient

EXAMPLES = Path(__file__).parent.parent / "examples"
OOM = json.loads((EXAMPLES / "oomkilled.json").read_text())


def reply(evidence):
    return json.dumps({
        "summary": "OOM", "missing_information": [],
        "hypotheses": [{"cause": "Memory limit too low", "confidence": "high",
                        "evidence": evidence, "next_steps": ["kubectl top pod"]}],
    })


def test_grounded_citations_pass_on_real_example():
    a = call_llm(OOM, client=FakeClient(reply(["exit_code: 137", "reason: OOMKilled", "memory: 256Mi"])))
    a = verify_evidence_grounding(a, OOM)
    assert a.hypotheses[0].unverified_evidence == []
    assert not a.hypotheses[0].cause.startswith("[UNVERIFIED")


def test_invented_citation_flagged():
    a = call_llm(OOM, client=FakeClient(reply(["exit_code: 137", "kernel: Out of memory: Killed process 99 (java)"])))
    a = verify_evidence_grounding(a, OOM)
    h = a.hypotheses[0]
    assert h.unverified_evidence == ["kernel: Out of memory: Killed process 99 (java)"]
    assert h.cause.startswith("[UNVERIFIED CITATION]")
    verify_evidence_grounding(a, OOM)  # idempotent: prefix not doubled
    assert h.cause.count("[UNVERIFIED CITATION]") == 1


def test_fenced_json_accepted():
    a = call_llm(OOM, client=FakeClient("```json\n" + reply(["x"]) + "\n```"))
    assert a.summary == "OOM"


@pytest.mark.parametrize("text, stop", [
    ("sorry, no", "end_turn"), ("", "end_turn"),
    ('{"summary": "x"}', "end_turn"), ('{"summary": "tru', "max_tokens"),
])
def test_bad_output_raises_analysis_error(text, stop):
    with pytest.raises(AnalysisError):
        call_llm(OOM, client=FakeClient(text, stop))


def test_library_call_has_no_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(AnalysisError):
        call_llm(OOM, client=FakeClient("nope"))
    assert list(tmp_path.iterdir()) == []  # no stray evidence.json, no sys.exit
