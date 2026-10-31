"""Where the log comes from: a file, stdin, a GitHub run or a Jenkins build.

All reads keep only the last MAX_BYTES of a log. Failures are at the end,
and a multi-hundred-megabyte log should not be able to exhaust memory.
`gh` and the HTTP opener are injectable so tests need no network.
"""

import base64
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Callable, Optional

MAX_BYTES = 5 * 1024 * 1024


class SourceError(Exception):
    """The log could not be read or fetched."""


def _tail(data: bytes) -> str:
    return data[-MAX_BYTES:].decode("utf-8", errors="replace")


def read_file(path: str) -> str:
    try:
        if path == "-":
            return _tail(sys.stdin.buffer.read())
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - MAX_BYTES))
            return _tail(f.read())
    except OSError as exc:
        raise SourceError(f"cannot read {path}: {exc.strerror or exc}") from exc


def fetch_github_run(run_id: str, repo: str, runner: Callable = subprocess.run) -> str:
    """Failed-step logs of a GitHub Actions run, through the `gh` CLI."""
    if not run_id.isdigit():
        raise SourceError("--gh-run needs a numeric run id")
    if repo.count("/") != 1 or repo.startswith("-"):
        raise SourceError("--repo must look like owner/name")
    try:
        out = runner(["gh", "run", "view", run_id, "--repo", repo, "--log-failed"],
                     capture_output=True, timeout=120)
    except FileNotFoundError as exc:
        raise SourceError("the gh CLI is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise SourceError("gh timed out") from exc
    if out.returncode != 0:
        detail = (out.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()
        raise SourceError(f"gh failed: {detail[-1] if detail else 'unknown error'}")
    return _tail(out.stdout)


def fetch_jenkins(url: str, user: Optional[str] = None, token: Optional[str] = None,
                  opener: Callable = urllib.request.urlopen) -> str:
    """Console text of a Jenkins build, e.g. https://ci.example.com/job/app/42/"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SourceError("--jenkins-url must be an http(s) URL")
    if not parsed.path.rstrip("/").endswith("consoleText"):
        url = url.rstrip("/") + "/consoleText"
    request = urllib.request.Request(url)
    if user and token:
        request.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{token}".encode()).decode())
    try:
        with opener(request, timeout=30) as resp:
            return _tail(resp.read())
    except Exception as exc:
        raise SourceError(f"could not fetch the Jenkins log ({type(exc).__name__})") from exc
