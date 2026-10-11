"""Shared fakes and builders — no GitHub, no network and no API key required."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_LOG = ROOT / "examples" / "sample_build.log"

GOOD_DIAGNOSIS = (
    "**Root cause:** `applyDiscount()` calls `reduce` on an empty `items` array "
    "without an initial value, so it throws for an empty cart.\n\n"
    "**Where:** `src/cart.js:42`\n\n"
    "**Suggested fix:** Return `0` early when `items.length === 0`."
)


class FakeResponse:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [SimpleNamespace(type="text", text=text)]
        self.stop_reason = stop_reason


class FakeClient:
    """Stands in for anthropic.Anthropic; records every request."""

    def __init__(self, text=GOOD_DIAGNOSIS, stop_reason="end_turn", raises=None):
        self.calls = []
        self._response = FakeResponse(text, stop_reason)
        self._raises = raises
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise self._raises
        return self._response

    @property
    def prompt(self):
        return self.calls[-1]["messages"][0]["content"]


class FakeGh:
    """Stands in for subprocess.run when the code calls the `gh` CLI."""

    def __init__(self, changed=None, fail_files=False, fail_inline=False, fail_pr=False):
        self.calls = []
        self.changed = changed or {}  # {path: unified-diff patch}
        self.fail_files, self.fail_inline, self.fail_pr = fail_files, fail_inline, fail_pr

    def __call__(self, cmd, **kwargs):
        assert isinstance(cmd, list), "gh must be called with an argument list, never a shell string"
        self.calls.append(cmd)
        endpoint = next((a for a in cmd if a.startswith("repos/")), "")
        if endpoint.endswith("/files"):
            if self.fail_files:
                return self._done(cmd, 1, stderr="HTTP 404")
            out = "\n".join(json.dumps([name, patch]) for name, patch in self.changed.items())
            return self._done(cmd, 0, out)
        if "/pulls/" in endpoint and endpoint.endswith("/comments"):
            return self._done(cmd, 1 if self.fail_inline else 0,
                              stderr="HTTP 422 line must be part of the diff" if self.fail_inline else "")
        if "/issues/" in endpoint and endpoint.endswith("/comments"):
            return self._done(cmd, 1 if self.fail_pr else 0,
                              stderr="HTTP 403" if self.fail_pr else "")
        return self._done(cmd, 1, stderr="unexpected call")

    @staticmethod
    def _done(cmd, code, stdout="", stderr=""):
        return subprocess.CompletedProcess(cmd, code, stdout, stderr)

    @property
    def kinds(self):
        """Which kind of call was made, in order: files / inline / pr."""
        names = []
        for cmd in self.calls:
            endpoint = next(a for a in cmd if a.startswith("repos/"))
            if endpoint.endswith("/files"):
                names.append("files")
            elif "/pulls/" in endpoint:
                names.append("inline")
            else:
                names.append("pr")
        return names


def field(cmd, key):
    """Value of a `-f key=value` / `-F key=value` argument in a gh call."""
    prefix = key + "="
    return next(a[len(prefix):] for a in cmd if a.startswith(prefix))


def long_log(total_lines=4000):
    """A realistic 4,000-line raw log: thousands of harmless lines, then the
    real failure captured from the demo app at the very end."""
    tail = SAMPLE_LOG.read_text(errors="ignore").splitlines()
    filler = [f"PASS  src/generated/module{i}.test.js ({i % 9 + 1} ms)"
              for i in range(total_lines - len(tail))]
    return "\n".join(filler + tail) + "\n"


@pytest.fixture
def sample_log():
    return SAMPLE_LOG.read_text(errors="ignore")
