"""Step 1: turn a raw CI log into plain, redacted lines.

GitHub Actions and Jenkins both decorate every line: timestamps, ANSI
colors, progress bars that rewrite one line with carriage returns, and
(for `gh run view --log-failed`) a `job<TAB>step<TAB>` prefix. None of
that helps a reader or an LLM, and a timestamp in front of an error can
hide it from a pattern anchored on the start of the line.

Order matters: collapse carriage returns, strip ANSI and control
characters, strip CI prefixes, then redact secrets. The result is the
exact text every later step sees, and the text the grounding check
compares the model's quotes against.
"""

import re
from typing import List, Tuple

from src.redactor import redact

_ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]"          # CSI  ESC [ ... final-byte
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"       # OSC  ESC ] ... BEL or ST
    r"|[@-Z\\-_])"                           # Fe   ESC + one character
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# `gh run view --log-failed` prints:  <job>\t<step>\t<timestamp> <line>
_GH_CLI_PREFIX = re.compile(r"^[^\t\n]+\t[^\t\n]+\t")
# GitHub Actions raw logs: 2026-10-30T09:15:02.1234567Z <line>
_GH_TIMESTAMP = re.compile(r"^﻿?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z ?")
# Jenkins Timestamper plugin: [2026-10-30T09:15:02.123Z] <line>
_JENKINS_TIMESTAMP = re.compile(r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\] ?")


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def collapse_carriage_returns(text: str) -> str:
    """Keep only what a terminal would finally show on each line."""
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if "\r" in line:
            segments = [s for s in line.split("\r") if s]
            line = segments[-1] if segments else ""
        out.append(line)
    return "\n".join(out)


def strip_prefixes(line: str) -> str:
    line = _GH_CLI_PREFIX.sub("", line, count=1)
    line = _GH_TIMESTAMP.sub("", line, count=1)
    line = _JENKINS_TIMESTAMP.sub("", line, count=1)
    return line.rstrip()


def normalize(raw: str) -> Tuple[str, List[str]]:
    """Raw log in; (clean text, clean lines) out. Secrets are redacted."""
    text = collapse_carriage_returns(raw)
    text = strip_ansi(text)
    text = _CONTROL.sub("", text)
    lines = [strip_prefixes(line) for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    clean = redact("\n".join(lines))
    return clean, clean.split("\n") if clean else []
