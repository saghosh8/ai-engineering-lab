import pytest

from src import cli
from src.github_client import GitHubError, PostOutcome
from src.extractor import Location
from tests.conftest import SAMPLE_LOG, FakeClient

SHA = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    """No .env file, no real keys, and the model is always faked."""
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("src.llm_client.Anthropic", lambda **kwargs: FakeClient())
    for name in ("REPO", "PR_NUMBER", "HEAD_SHA", "GITHUB_WORKSPACE", "TRIAGE_MODEL", "ANTHROPIC_MODEL"):
        monkeypatch.delenv(name, raising=False)


def set_pr_env(monkeypatch, repo="octo/shop", pr="7", sha=SHA):
    monkeypatch.setenv("REPO", repo)
    monkeypatch.setenv("PR_NUMBER", pr)
    monkeypatch.setenv("HEAD_SHA", sha)


def test_missing_api_key_skips_quietly_instead_of_failing(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert cli.main([str(SAMPLE_LOG)]) == 0
    assert "Skipping AI triage" in capsys.readouterr().out


def test_unreadable_log_file_is_an_error(capsys):
    assert cli.main(["/no/such/build.log"]) == 2
    assert "Cannot read log file" in capsys.readouterr().err


def test_dry_run_prints_the_comment_and_posts_nothing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "post_comment", lambda *a, **k: pytest.fail("must not post in a dry run"))
    assert cli.main([str(SAMPLE_LOG), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "COMMENT THAT WOULD BE POSTED" in out
    assert "src/cart.js:42" in out
    assert "CI Triage Bot" in out


def test_posts_the_comment_with_the_values_from_the_environment(monkeypatch, capsys):
    set_pr_env(monkeypatch)
    sent = {}

    def fake_post(repo, pr, sha, body, locations):
        sent.update(repo=repo, pr=pr, sha=sha, body=body, locations=locations)
        return PostOutcome("inline", Location("app/src/cart.js", 42))

    monkeypatch.setattr(cli, "post_comment", fake_post)
    assert cli.main([str(SAMPLE_LOG)]) == 0
    assert (sent["repo"], sent["pr"], sent["sha"]) == ("octo/shop", 7, SHA)
    assert "CI Triage Bot" in sent["body"]
    assert sent["locations"][0] == Location("src/cart.js", 42)
    assert "inline at app/src/cart.js:42" in capsys.readouterr().out


@pytest.mark.parametrize("env", [
    {"repo": "not-a-repo"},
    {"pr": "seven"},
    {"sha": "not a sha; rm -rf /"},
])
def test_malformed_environment_values_are_rejected_before_any_call(monkeypatch, capsys, env):
    set_pr_env(monkeypatch, **env)
    monkeypatch.setattr(cli, "post_comment", lambda *a, **k: pytest.fail("must not post"))
    assert cli.main([str(SAMPLE_LOG)]) == 1
    assert "Could not post" in capsys.readouterr().err


def test_github_failure_is_reported_as_a_step_failure(monkeypatch, capsys):
    set_pr_env(monkeypatch)

    def boom(*args, **kwargs):
        raise GitHubError("gh api failed (exit 1): HTTP 403")

    monkeypatch.setattr(cli, "post_comment", boom)
    assert cli.main([str(SAMPLE_LOG)]) == 1
    assert "HTTP 403" in capsys.readouterr().err


def test_model_outage_still_posts_the_raw_trace(monkeypatch, capsys):
    set_pr_env(monkeypatch)
    monkeypatch.setattr("src.llm_client.Anthropic", lambda **kwargs: FakeClient(raises=TimeoutError("slow")))
    bodies = []
    monkeypatch.setattr(cli, "post_comment",
                        lambda repo, pr, sha, body, locs: bodies.append(body) or PostOutcome("pr", None))
    assert cli.main([str(SAMPLE_LOG)]) == 0
    assert "<details>" in bodies[0]
    assert "AI diagnosis unavailable" in capsys.readouterr().out
