import json

import pytest

from src import cli
from src.sources import SourceError
from tests.conftest import EXAMPLES


def run(capsys, *argv):
    code = cli.main(list(argv))
    return code, capsys.readouterr()


def test_markdown_report_for_a_file(capsys):
    code, out = run(capsys, "--no-llm", str(EXAMPLES / "jenkins_docker_auth.log"))
    assert code == 0 and "Authentication or permission error" in out.out and "Push image" in out.out


def test_json_output(capsys):
    _, out = run(capsys, "--no-llm", "--format", "json", str(EXAMPLES / "gha_test_failure.log"))
    assert json.loads(out.out)["category"] == "test_failure"


def test_exactly_one_source_is_required(capsys):
    with pytest.raises(SystemExit):
        cli.main([])
    with pytest.raises(SystemExit):
        cli.main(["a.log", "--jenkins-url", "https://ci.example.com/job/a/1/"])


def test_gh_run_needs_repo():
    with pytest.raises(SystemExit):
        cli.main(["--gh-run", "123"])


def test_missing_file_exits_2_with_a_message(capsys):
    code, out = run(capsys, "nope.log")
    assert code == 2 and "error: cannot read" in out.err


def test_gh_run_path(monkeypatch, capsys):
    monkeypatch.setattr(cli, "fetch_github_run", lambda run_id, repo: (EXAMPLES / "gha_network_flake.log").read_text())
    code, out = run(capsys, "--no-llm", "--gh-run", "99", "--repo", "me/app")
    assert code == 0 and "Network or registry problem" in out.out


def test_jenkins_path_uses_env_credentials(monkeypatch, capsys):
    seen = {}

    def fake(url, user, token):
        seen.update(url=url, user=user, token=token)
        return (EXAMPLES / "jenkins_out_of_memory.log").read_text()

    monkeypatch.setattr(cli, "fetch_jenkins", fake)
    monkeypatch.setenv("JENKINS_USER", "u")
    monkeypatch.setenv("JENKINS_TOKEN", "t")
    code, out = run(capsys, "--no-llm", "--jenkins-url", "https://ci.example.com/job/a/1/")
    assert code == 0 and seen == {"url": "https://ci.example.com/job/a/1/", "user": "u", "token": "t"}
    assert "Out of memory" in out.out


def test_fetch_error_exits_2(monkeypatch, capsys):
    def boom(*a):
        raise SourceError("gh failed: HTTP 404")

    monkeypatch.setattr(cli, "fetch_github_run", boom)
    code, out = run(capsys, "--gh-run", "1", "--repo", "a/b")
    assert code == 2 and "HTTP 404" in out.err
