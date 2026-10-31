import io
import subprocess
from types import SimpleNamespace

import pytest

from src import sources
from src.sources import SourceError, fetch_github_run, fetch_jenkins, read_file


def test_reads_a_file(tmp_path):
    p = tmp_path / "a.log"
    p.write_text("hello")
    assert read_file(str(p)) == "hello"


def test_only_the_tail_of_a_huge_file_is_read(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "MAX_BYTES", 10)
    p = tmp_path / "big.log"
    p.write_text("0123456789ABCDEFGHIJ")
    assert read_file(str(p)) == "ABCDEFGHIJ"


def test_missing_file_is_a_clean_error(tmp_path):
    with pytest.raises(SourceError, match="cannot read"):
        read_file(str(tmp_path / "nope.log"))


def test_reads_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", SimpleNamespace(buffer=io.BytesIO(b"from stdin")))
    assert read_file("-") == "from stdin"


def test_github_run_builds_the_gh_command():
    seen = {}

    def runner(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=b"log text", stderr=b"")

    assert fetch_github_run("123", "me/app", runner=runner) == "log text"
    assert seen["cmd"] == ["gh", "run", "view", "123", "--repo", "me/app", "--log-failed"]


@pytest.mark.parametrize("run_id,repo", [("12a", "me/app"), ("1", "noslash"), ("1", "-x/y"), ("1; rm", "a/b")])
def test_github_run_rejects_bad_arguments(run_id, repo):
    with pytest.raises(SourceError):
        fetch_github_run(run_id, repo, runner=lambda *a, **k: None)


def test_github_run_errors():
    fail = lambda *a, **k: SimpleNamespace(returncode=1, stdout=b"", stderr=b"HTTP 404: Not Found\n")
    with pytest.raises(SourceError, match="HTTP 404"):
        fetch_github_run("1", "a/b", runner=fail)

    def missing(*a, **k):
        raise FileNotFoundError

    with pytest.raises(SourceError, match="not installed"):
        fetch_github_run("1", "a/b", runner=missing)

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("gh", 120)

    with pytest.raises(SourceError, match="timed out"):
        fetch_github_run("1", "a/b", runner=slow)


class FakeHTTP:
    def __init__(self, body=b"console text"):
        self.body, self.request = body, None

    def __call__(self, request, timeout):
        self.request = request
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def test_jenkins_appends_console_text_and_sends_basic_auth():
    http = FakeHTTP()
    assert fetch_jenkins("https://ci.example.com/job/app/42/", "u", "t", opener=http) == "console text"
    assert http.request.full_url == "https://ci.example.com/job/app/42/consoleText"
    assert http.request.get_header("Authorization").startswith("Basic ")


def test_jenkins_url_already_pointing_at_console_text_is_kept():
    http = FakeHTTP()
    fetch_jenkins("https://ci.example.com/job/app/42/consoleText", opener=http)
    assert http.request.full_url.endswith("/42/consoleText")
    assert http.request.get_header("Authorization") is None


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://x/y", "not a url", "https://"])
def test_jenkins_rejects_non_http_urls(url):
    with pytest.raises(SourceError):
        fetch_jenkins(url, opener=FakeHTTP())


def test_jenkins_network_error_is_wrapped_without_leaking_details():
    def boom(*a, **k):
        raise OSError("secret-host refused")

    with pytest.raises(SourceError) as exc:
        fetch_jenkins("https://ci.example.com/job/a/1/", opener=boom)
    assert "OSError" in str(exc.value) and "secret-host" not in str(exc.value)
