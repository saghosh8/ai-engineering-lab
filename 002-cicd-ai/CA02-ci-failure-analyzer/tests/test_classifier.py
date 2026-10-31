import pytest

from src.classifier import classify
from src.normalizer import normalize
from tests.conftest import sample


def top(name):
    return classify(normalize(sample(name))[1])


@pytest.mark.parametrize("name,expected", [
    ("gha_dependency_404.log", "dependency_install"),
    ("gha_test_failure.log", "test_failure"),
    ("gha_network_flake.log", "network"),
    ("jenkins_out_of_memory.log", "out_of_memory"),
    ("jenkins_docker_auth.log", "auth_permission"),
])
def test_samples_rank_the_right_category_first(name, expected):
    assert top(name)[0].category == expected


def test_out_of_memory_outranks_the_test_it_broke():
    cats = [c.category for c in top("jenkins_out_of_memory.log")]
    assert cats[:2] == ["out_of_memory", "test_failure"]


def test_evidence_carries_one_based_line_numbers_and_text():
    lines = normalize(sample("jenkins_docker_auth.log"))[1]
    ev = classify(lines)[0].evidence[0]
    assert lines[ev.line_no - 1].strip() == ev.text
    assert "denied" in ev.text


def test_only_the_last_three_matches_are_kept_but_all_are_counted():
    lines = [f"ECONNRESET on attempt {i}" for i in range(7)]
    c = classify(lines)[0]
    assert c.matches == 7 and [e.line_no for e in c.evidence] == [5, 6, 7]


def test_later_matches_score_higher():
    early = classify(["ETIMEDOUT"] + ["ok"] * 20)[0].score
    late = classify(["ok"] * 20 + ["ETIMEDOUT"])[0].score
    assert late > early


def test_same_log_same_ranking():
    assert top("jenkins_out_of_memory.log") == top("jenkins_out_of_memory.log")


def test_clean_log_has_no_candidates():
    assert classify(["Run npm test", "all 42 tests passed", "Finished: SUCCESS"]) == []


def test_finished_failure_is_not_a_test_failure():
    assert classify(["Finished: FAILURE"]) == []


def test_long_evidence_lines_are_cut():
    c = classify(["ETIMEDOUT " + "x" * 1000])[0]
    assert len(c.evidence[0].text) <= 240
