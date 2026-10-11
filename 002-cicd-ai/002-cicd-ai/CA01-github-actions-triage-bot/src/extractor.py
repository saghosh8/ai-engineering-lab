"""Step 3 of the pipeline: find the terminal stack trace.

The root cause of a failed build is almost always near the *end* of the
log. Build tools repeat the same error many times, or print harmless
warnings early on; the last real error is the one that stopped the build.
So we find the last error-looking line and keep a small window of lines
around it — a few dozen lines instead of thousands.

This is a parsing problem, not an interpretation problem, so it stays
outside the LLM entirely.
"""

import re
from dataclasses import dataclass
from typing import List, Optional

# Lines that look like the failure itself.
_ERROR_HINTS = re.compile(
    r"Traceback|Error:|Exception|FAIL|panic:|✕|\berror:|FATAL|npm ERR!|npm error"
)
# Footer lines that tools print *after* the real error ("npm ERR! Test
# failed", "make: *** [all] Error 1"). They are hints too, but they make a
# bad anchor, so they are only used when nothing better exists.
_FOOTER = re.compile(
    r"^\s*(?:npm (?:ERR!|error|notice)|make(?:\[\d+\])?: \*\*\*|##\[error\]|Error: Process completed)"
)

_EXTENSIONS = (
    "py|jsx|js|mjs|cjs|tsx|ts|go|java|kt|rb|rs|cpp|cc|c|hpp|h|cs|php|swift|scala"
)
# src/cart.js:42   src/cart.js:42:26   Foo.java:42   main.rs:12:5
_FILE_LINE = re.compile(rf"(?P<path>[\w./@+\-]+\.(?:{_EXTENSIONS})):(?P<line>\d+)")
# Python:  File "/home/runner/work/app/app/src/cart.py", line 42, in apply
_PY_FRAME = re.compile(r'File "(?P<path>[^"]+\.py)", line (?P<line>\d+)')

# Frames inside dependencies or the runtime are never the place to comment.
_VENDOR = (
    "node_modules/", "site-packages/", "dist-packages/", "/usr/lib/",
    "/usr/local/lib/", "/opt/hostedtoolcache/", "/rustc/", "/usr/local/go/",
)

MAX_LINE_CHARS = 400


@dataclass(frozen=True)
class Location:
    """A file and line mentioned in the trace."""

    path: str
    line: int


@dataclass(frozen=True)
class Trace:
    """The slice of the log that gets sent to the LLM."""

    text: str
    start: int                 # 1-based number of the first line kept
    end: int                   # 1-based number of the last line kept
    total_lines: int           # lines in the whole cleaned log
    hit_line: Optional[int]    # 1-based line of the error we anchored on

    @property
    def lines_sent(self) -> int:
        return 0 if not self.text else self.end - self.start + 1

    @property
    def fraction(self) -> float:
        return self.lines_sent / self.total_lines if self.total_lines else 0.0


def _find_anchor(lines: List[str]) -> Optional[int]:
    hits = [i for i, line in enumerate(lines) if _ERROR_HINTS.search(line)]
    real = [i for i in hits if not _FOOTER.search(lines[i])]
    chosen = real or hits
    return chosen[-1] if chosen else None


def extract_trace(log: str, before: int = 40, after: int = 15) -> Trace:
    """Keep `before` lines up to and including the last error line, plus
    the lines after it (55 lines in total with the defaults).

    If nothing in the log looks like an error, fall back to the tail of
    the log: the end is still the best guess.
    """
    lines = log.splitlines()
    if not lines:
        return Trace(text="", start=0, end=0, total_lines=0, hit_line=None)

    anchor = _find_anchor(lines)
    if anchor is None:
        start, end = max(0, len(lines) - (before + after)), len(lines)
    else:
        start, end = max(0, anchor - before), min(len(lines), anchor + after)
        end = max(end, anchor + 1)

    kept = [
        line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS] + " …"
        for line in lines[start:end]
    ]
    return Trace(
        text="\n".join(kept),
        start=start + 1,
        end=end,
        total_lines=len(lines),
        hit_line=None if anchor is None else anchor + 1,
    )


def _relative(path: str, workspace: Optional[str]) -> str:
    """Make a path relative to the checkout when we can tell where it is."""
    if workspace:
        prefix = workspace.rstrip("/") + "/"
        if path.startswith(prefix):
            path = path[len(prefix):]
    return path[2:] if path.startswith("./") else path


def find_locations(trace_text: str, workspace: Optional[str] = None) -> List[Location]:
    """File:line references in the trace, most likely failure site first.

    JavaScript, Java, Go and Rust print the failing frame first. Python
    prints it last ("most recent call last"), so that order is reversed.
    Dependency and runtime frames are skipped; duplicates are dropped.
    """
    found = []
    for pattern in (_FILE_LINE, _PY_FRAME):
        for m in pattern.finditer(trace_text):
            found.append((m.start(), m.group("path"), int(m.group("line"))))
    found.sort()

    seen, locations = set(), []
    for _, raw_path, line in found:
        if any(v in raw_path for v in _VENDOR):
            continue
        path = _relative(raw_path, workspace)
        if (path, line) in seen:
            continue
        seen.add((path, line))
        locations.append(Location(path, line))

    if "Traceback (most recent call last)" in trace_text:
        locations.reverse()
    return locations
