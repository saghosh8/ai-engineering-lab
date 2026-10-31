import re

import pytest

from src.analyzer import analyze
from tests.conftest import FakeClient, diagnosis_json, sample

DEP = sample("gha_dependency_404.log")


def test_full_pipeline_with_a_fake_model():
    client = FakeClient()
    r = analyze(DEP, client=client)
    assert r.llm_used and r.category == "dependency_install" and r.ci == "github-actions"
    assert r.step == "Run npm ci" and len(client.calls) == 1
    assert r.diagnosis["evidence"] and r.notes == []


def test_prompt_contains_hints_and_the_excerpt_but_no_timestamps():
    client = FakeClient()
    analyze(DEP, client=client)
    sent = client.calls[0]["messages"][0]["content"]
    assert "dependency_install" in sent and "npm error code E404" in sent
    assert not re.search(r"\d{2}:\d{2}:\d{2}\.\d{7}Z", sent)   # line prefixes are gone


def test_secrets_never_reach_the_model():
    secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    client = FakeClient()
    analyze(DEP + f"export GITHUB_TOKEN={secret}\nnpm error code E404\n", client=client)
    assert secret not in client.calls[0]["messages"][0]["content"]


def test_no_llm_flag_gives_rule_based_result_and_no_call():
    client = FakeClient()
    r = analyze(DEP, use_llm=False, client=client)
    assert not r.llm_used and r.category == "dependency_install" and not client.calls
    assert "--no-llm" in r.llm_skipped_reason


def test_missing_api_key_falls_back(no_api_key):
    r = analyze(DEP)
    assert not r.llm_used and r.category == "dependency_install"
    assert "ANTHROPIC_API_KEY" in r.llm_skipped_reason


def test_api_error_falls_back_without_crashing():
    r = analyze(DEP, client=FakeClient(raises=RuntimeError("boom with key sk-secret")))
    assert not r.llm_used and "RuntimeError" in r.llm_skipped_reason
    assert "sk-secret" not in r.llm_skipped_reason and r.category == "dependency_install"


def test_garbage_model_output_falls_back():
    r = analyze(DEP, client=FakeClient(text="I think it is the network."))
    assert not r.llm_used and "rejected" in r.llm_skipped_reason


def test_fabricated_evidence_is_removed_and_confidence_lowered():
    r = analyze(DEP, client=FakeClient(text=diagnosis_json(evidence=["segfault in libfoo"])))
    assert r.diagnosis["evidence"] == [] and r.diagnosis["confidence"] == "low" and r.notes


def test_disagreement_with_rules_is_flagged_and_high_confidence_capped():
    r = analyze(DEP, client=FakeClient(text=diagnosis_json(category="network")))
    assert r.diagnosis["confidence"] == "medium"
    assert any("rules ranked" in n for n in r.notes)


def test_unknown_from_the_model_keeps_the_rule_based_headline():
    r = analyze(DEP, client=FakeClient(text=diagnosis_json(category="unknown", confidence="low", evidence=[])))
    assert r.category == "dependency_install"


def test_successful_log_is_not_sent_to_the_model():
    client = FakeClient()
    r = analyze("Run npm test\nall 42 tests passed\nFinished: SUCCESS\n", client=client)
    assert not r.failed and not client.calls and "No failure" in r.notes[0]


def test_empty_log():
    r = analyze("", client=FakeClient())
    assert not r.failed and r.notes == ["The log is empty."]


def test_unrecognised_failure_still_goes_to_the_model_with_no_hints():
    client = FakeClient(text=diagnosis_json(category="unknown", confidence="low", evidence=[]))
    r = analyze("starting\nERROR: something odd happened\n", client=client)
    assert r.failed and r.candidates == [] and client.calls
    assert "no known failure pattern matched" in client.calls[0]["messages"][0]["content"]


def test_ci_can_be_forced():
    assert analyze(DEP, ci="jenkins", use_llm=False).ci == "jenkins"
    assert analyze(DEP, ci="bogus", use_llm=False).ci == "github-actions"


@pytest.mark.parametrize("log", [
    "=== 15 passed, 0 failed in 2.1s ===\nFinished: SUCCESS\n",
    "Tests: 0 failed, 42 passed\n##[group]Run ok\nDone\n",
    "[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 1\nFinished: SUCCESS\n",
    "Build finished with exit code 0\n",
])
def test_passing_logs_are_not_reported_as_failures(log):
    client = FakeClient()
    r = analyze(log, client=client)
    assert not r.failed and r.candidates == [] and not client.calls


def test_zero_tests_failed_is_not_a_failure():
    assert not analyze("0 tests failed\n", use_llm=False).failed
