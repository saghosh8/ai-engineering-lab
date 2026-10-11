"""Guards the workflow file: the behaviour the article promises must not
silently regress when someone edits the YAML."""

from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / "workflow" / "ca01-triage-demo.yml"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


@pytest.fixture(scope="module")
def steps(workflow):
    return {s.get("id") or s.get("name"): s for s in workflow["jobs"]["test"]["steps"] if "name" in s or "id" in s}


def test_runs_on_pull_requests_only_never_pull_request_target(workflow):
    triggers = workflow.get("on") or workflow.get(True)  # YAML 1.1 reads `on` as True
    assert "pull_request" in triggers
    assert "pull_request_target" not in triggers


def test_permissions_are_minimal(workflow):
    assert workflow["permissions"] == {"contents": "read", "pull-requests": "write"}


def test_test_step_survives_failure_and_keeps_the_exit_code(steps):
    tests = steps["tests"]
    assert tests["continue-on-error"] is True
    assert "tee" in tests["run"]
    assert "PIPESTATUS[0]" in tests["run"]
    assert tests["env"]["FORCE_COLOR"] == "1"


def test_triage_runs_only_after_a_failure_and_never_for_forks(steps):
    cond = steps["AI triage"]["if"]
    assert "steps.tests.outcome == 'failure'" in cond
    assert "github.event.pull_request.head.repo.full_name == github.repository" in cond


def test_triage_gets_exactly_the_environment_the_cli_reads(steps):
    env = steps["AI triage"]["env"]
    assert set(env) == {"ANTHROPIC_API_KEY", "GH_TOKEN", "PR_NUMBER", "REPO", "HEAD_SHA"}
    assert env["ANTHROPIC_API_KEY"] == "${{ secrets.ANTHROPIC_API_KEY }}"
    assert "python -m src.cli" in steps["AI triage"]["run"]


def test_a_broken_bot_cannot_hide_the_real_failure(steps):
    assert steps["AI triage"]["continue-on-error"] is True
    last = steps["Fail the job"]
    assert last["if"] == "steps.tests.outcome == 'failure'"
    assert last["run"] == "exit 1"


def test_step_order(workflow):
    ids = [s.get("id") or s.get("name") for s in workflow["jobs"]["test"]["steps"]]
    assert ids.index("tests") < ids.index("AI triage") < ids.index("Fail the job")
    assert ids[-1] == "Fail the job"
