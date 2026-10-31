import pytest

from src.detector import GITHUB, JENKINS, UNKNOWN, detect_ci, find_failed_step
from src.normalizer import normalize
from tests.conftest import sample


def lines_of(name):
    return normalize(sample(name))[1]


@pytest.mark.parametrize("name,expected", [
    ("gha_dependency_404.log", GITHUB),
    ("gha_test_failure.log", GITHUB),
    ("gha_network_flake.log", GITHUB),
    ("jenkins_out_of_memory.log", JENKINS),
    ("jenkins_docker_auth.log", JENKINS),
])
def test_detects_ci_system(name, expected):
    assert detect_ci(lines_of(name)) == expected


def test_unknown_when_no_signals():
    assert detect_ci(["hello", "world"]) == UNKNOWN


def test_github_failed_step_is_group_above_last_error():
    lines = lines_of("gha_test_failure.log")
    assert find_failed_step(lines, GITHUB) == "Run pytest -q"


def test_jenkins_failed_stage_is_marker_above_error():
    assert find_failed_step(lines_of("jenkins_docker_auth.log"), JENKINS) == "Push image"
    assert find_failed_step(lines_of("jenkins_out_of_memory.log"), JENKINS) == "Build"


def test_no_step_when_no_error_or_unknown_ci():
    assert find_failed_step(["##[group]Run ok", "fine"], GITHUB) is None
    assert find_failed_step(["x"], UNKNOWN) is None
