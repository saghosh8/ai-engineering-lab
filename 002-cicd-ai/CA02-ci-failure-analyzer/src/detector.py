"""Step 2: which CI system produced this log, and which step failed.

Both are plain pattern checks. The failed step is not a guess: for
GitHub Actions it is the `##[group]` header above the last `##[error]`
line, and for Jenkins it is the `[Pipeline] { (Stage)` marker above the
last error line.
"""

import re
from typing import List, Optional

GITHUB = "github-actions"
JENKINS = "jenkins"
UNKNOWN = "unknown"
CI_SYSTEMS = (GITHUB, JENKINS)

_GITHUB_SIGNALS = [
    re.compile(r"##\[(?:group|endgroup|error|warning|debug)\]"),
    re.compile(r"^Run [\w./@-]+"),
    re.compile(r"^Post job cleanup\.?$"),
    re.compile(r"^Complete job name:"),
    re.compile(r"^Current runner version:"),
]
_JENKINS_SIGNALS = [
    re.compile(r"^\[Pipeline\]"),
    re.compile(r"^Started by "),
    re.compile(r"^Running on \S+"),
    re.compile(r"^Finished: (?:SUCCESS|FAILURE|UNSTABLE|ABORTED)"),
    re.compile(r"^Running in Durability level"),
    re.compile(r"^hudson\.|^org\.jenkinsci\."),
]

_GH_GROUP = re.compile(r"##\[group\](.*)")
_GH_ERROR = re.compile(r"##\[error\]")
_JK_STAGE = re.compile(r"^\[Pipeline\] \{ \((.+)\)\s*$")
_JK_ERROR = re.compile(r"^(?:ERROR:|hudson\.AbortException|.*script returned exit code [1-9])")


def detect_ci(lines: List[str]) -> str:
    """Count signals for each system; the clear winner decides."""
    gh = sum(1 for line in lines for p in _GITHUB_SIGNALS if p.search(line))
    jk = sum(1 for line in lines for p in _JENKINS_SIGNALS if p.search(line))
    if gh == 0 and jk == 0:
        return UNKNOWN
    return GITHUB if gh >= jk else JENKINS


def find_failed_step(lines: List[str], ci: str) -> Optional[str]:
    """Name of the step (GitHub) or stage (Jenkins) that holds the last error."""
    if ci == GITHUB:
        errors = [i for i, line in enumerate(lines) if _GH_ERROR.search(line)]
        if not errors:
            return None
        for i in range(errors[-1], -1, -1):
            m = _GH_GROUP.search(lines[i])
            if m:
                return m.group(1).strip() or None
        return None
    if ci == JENKINS:
        errors = [i for i, line in enumerate(lines) if _JK_ERROR.search(line)]
        if not errors:
            return None
        for i in range(errors[-1], -1, -1):
            m = _JK_STAGE.match(lines[i])
            if m:
                return m.group(1).strip()
        return None
    return None
