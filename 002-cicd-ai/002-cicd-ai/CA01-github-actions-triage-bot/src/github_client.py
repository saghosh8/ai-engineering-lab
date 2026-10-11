"""Everything that talks to GitHub, through the `gh` CLI.

`gh` is preinstalled on GitHub-hosted runners and reads GH_TOKEN from the
environment, so the bot needs no extra dependency. Arguments are always
passed as a list (never through a shell), so a log line can't inject a
command.

Posting strategy
----------------
An *inline* review comment is the best place for the diagnosis, but
GitHub only accepts one on a line that is part of the PR diff. So we:

1. read which lines the PR changed,
2. pick the first file:line from the trace that is one of them,
3. try an inline comment there,
4. and fall back to a normal PR comment if there is no such line or
   GitHub refuses the inline one.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set

from src.extractor import Location

Runner = Callable[..., "subprocess.CompletedProcess[str]"]

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


class GitHubError(RuntimeError):
    """A `gh` call failed."""


@dataclass(frozen=True)
class PostOutcome:
    kind: str                        # "inline" or "pr"
    location: Optional[Location]     # set when kind == "inline"
    note: Optional[str] = None       # why we fell back, when we did


def _gh(args: List[str], run: Optional[Runner] = None) -> "subprocess.CompletedProcess[str]":
    run = run or subprocess.run
    proc = run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()[:300]
        raise GitHubError(f"gh {args[0]} failed (exit {proc.returncode}): {detail}")
    return proc


def parse_patch(patch: str) -> Set[int]:
    """New-side line numbers that appear in a unified diff.

    Both added lines and unchanged context lines can carry an inline
    comment; removed lines have no new-side number.
    """
    lines: Set[int] = set()
    current = 0
    in_hunk = False
    for raw in patch.splitlines():
        header = _HUNK.match(raw)
        if header:
            current, in_hunk = int(header.group(1)), True
            continue
        if not in_hunk or raw.startswith("\\") or raw.startswith("-"):
            continue
        lines.add(current)
        current += 1
    return lines


def fetch_changed_lines(repo: str, pr: int, run: Optional[Runner] = None) -> Dict[str, Set[int]]:
    """{path: {line, ...}} for every file the PR touches."""
    proc = _gh(
        ["api", "--paginate", f"repos/{repo}/pulls/{pr}/files",
         "--jq", '.[] | [.filename, (.patch // "")] | @json'],
        run,
    )
    changed: Dict[str, Set[int]] = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, str):  # `gh --jq` prints raw strings; plain `jq` quotes them
            item = json.loads(item)
        filename, patch = item
        changed[filename] = parse_patch(patch)
    return changed


def _same_file(candidate: str, repo_path: str) -> bool:
    """`src/cart.js` from a test runner matches `app/src/cart.js` in the repo."""
    return repo_path == candidate or repo_path.endswith("/" + candidate)


def choose_location(locations: List[Location],
                    changed: Dict[str, Set[int]]) -> Optional[Location]:
    """First location from the trace that sits on a changed line, with the
    path rewritten to the repo-relative path GitHub expects."""
    for loc in locations:
        for path, lines in changed.items():
            if _same_file(loc.path, path) and loc.line in lines:
                return Location(path, loc.line)
    return None


def post_inline_comment(repo: str, pr: int, sha: str, loc: Location, body: str,
                        run: Optional[Runner] = None) -> None:
    _gh(
        ["api", f"repos/{repo}/pulls/{pr}/comments",
         "-f", f"body={body}", "-f", f"commit_id={sha}",
         "-f", f"path={loc.path}", "-F", f"line={loc.line}", "-f", "side=RIGHT"],
        run,
    )


def post_pr_comment(repo: str, pr: int, body: str, run: Optional[Runner] = None) -> None:
    _gh(["api", f"repos/{repo}/issues/{pr}/comments", "-f", f"body={body}"], run)


def post_comment(repo: str, pr: int, sha: str, body: str, locations: List[Location],
                 run: Optional[Runner] = None) -> PostOutcome:
    """Post `body` inline when possible, as a normal PR comment otherwise."""
    note = None
    if locations:
        try:
            target = choose_location(locations, fetch_changed_lines(repo, pr, run))
            if target is None:
                note = "no line from the trace is part of this PR's diff"
            else:
                try:
                    post_inline_comment(repo, pr, sha, target, body, run)
                    return PostOutcome("inline", target)
                except GitHubError as e:
                    note = f"inline comment refused: {e}"
        except GitHubError as e:
            note = f"could not read the PR diff: {e}"
    else:
        note = "no file:line found in the trace"

    post_pr_comment(repo, pr, body, run)
    return PostOutcome("pr", None, note)
