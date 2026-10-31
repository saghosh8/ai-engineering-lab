"""The workflow file is part of the product: check the properties that matter."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / "workflow" / "ca02-analyze-failed-run.yml"


def load():
    return yaml.safe_load(WORKFLOW.read_text())


def test_runs_after_another_workflow_completes():
    on = load()[True]                       # PyYAML reads the key `on` as boolean True
    assert on["workflow_run"]["types"] == ["completed"]


def test_only_failed_runs_are_analyzed():
    assert "conclusion == 'failure'" in load()["jobs"]["analyze"]["if"]


def test_permissions_are_minimal():
    assert load()["permissions"] == {"actions": "read", "contents": "read"}


def test_no_expression_is_interpolated_into_a_shell_script():
    for step in load()["jobs"]["analyze"]["steps"]:
        if "run" in step:
            assert "${{" not in step["run"], step["run"]


def test_values_reach_the_script_through_env():
    step = next(s for s in load()["jobs"]["analyze"]["steps"] if s.get("name") == "Analyze the failed run")
    assert set(step["env"]) >= {"ANTHROPIC_API_KEY", "GH_TOKEN", "RUN_ID", "REPO"}
    assert '"$RUN_ID"' in step["run"] and '"$REPO"' in step["run"]


def test_analyzer_step_runs_in_bash_with_pipefail_and_the_configured_folder():
    steps = load()["jobs"]["analyze"]["steps"]
    step = next(s for s in steps if s.get("name") == "Analyze the failed run")
    assert step["shell"] == "bash"
    assert all(s["working-directory"] == "${{ env.ANALYZER_DIR }}" for s in steps if "run" in s)
    assert "ANALYZER_DIR" in load()["env"]


def test_no_pull_request_target():
    assert "pull_request_target" not in WORKFLOW.read_text().split("\n", 6)[-1]


JENKINSFILE = WORKFLOW.parent.parent / "jenkins" / "Jenkinsfile.analyze-failure"


def test_jenkinsfile_passes_the_url_to_the_shell_not_to_groovy():
    text = JENKINSFILE.read_text()
    assert "python -m src.cli --jenkins-url \"$FAILED_BUILD_URL\"" in text
    assert "sh '''" in text                       # single-quoted: no Groovy interpolation
    assert "${params." not in text and "${FAILED_BUILD_URL}" not in text
    assert "withCredentials" in text and "ANTHROPIC_API_KEY" in text
