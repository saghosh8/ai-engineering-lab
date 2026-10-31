"""Shared fakes and builders: no network, no CI server and no API key required."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def sample(name: str) -> str:
    return (EXAMPLES / name).read_text()


def diagnosis_json(**overrides) -> str:
    base = {
        "category": "dependency_install",
        "likely_cause": "The package @acme/ui-kit is not in the npm registry the job uses.",
        "evidence": ["npm error 404 Not Found - GET https://registry.npmjs.org/@acme%2fui-kit - Not found"],
        "confidence": "high",
        "flaky_suspected": False,
        "next_steps": ["Check the package name and scope.", "Add an .npmrc with the private registry."],
    }
    base.update(overrides)
    return json.dumps(base)


class FakeResponse:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [SimpleNamespace(type="text", text=text)]
        self.stop_reason = stop_reason


class FakeClient:
    """Stands in for anthropic.Anthropic; records every request."""

    def __init__(self, text=None, stop_reason="end_turn", raises=None):
        self.calls = []
        self._response = FakeResponse(diagnosis_json() if text is None else text, stop_reason)
        self._raises = raises
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises:
            raise self._raises
        return self._response


@pytest.fixture
def no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
