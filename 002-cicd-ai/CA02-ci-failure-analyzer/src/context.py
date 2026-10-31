"""Step 4: pick what the model gets to see.

Never the whole log. We send three things:

1. the rule-based findings (the top candidates and their evidence lines)
   as *hints* the model may disagree with,
2. a window of numbered log lines around the strongest evidence, and
3. the last lines of the log, where `exit code` and the final verdict live.
"""

from typing import List, Optional, Tuple

from src.classifier import Candidate

BEFORE, AFTER, TAIL = 40, 15, 12
TOP_CANDIDATES = 3
MAX_EXCERPT_CHARS = 12000
MAX_LINE_CHARS = 400


def _ranges(lines: List[str], candidates: List[Candidate]) -> List[Tuple[int, int]]:
    """Index ranges (start inclusive, end exclusive) to include, merged."""
    n = len(lines)
    ranges = []
    if candidates:
        anchor = candidates[0].evidence[-1].line_no - 1
        ranges.append((max(0, anchor - BEFORE), min(n, anchor + AFTER + 1)))
    ranges.append((max(0, n - (TAIL if candidates else 60)), n))
    ranges.sort()
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def build_excerpt(lines: List[str], candidates: List[Candidate]) -> str:
    parts = []
    for start, end in _ranges(lines, candidates):
        parts.append("\n".join(f"L{i + 1}: {lines[i][:MAX_LINE_CHARS]}" for i in range(start, end)))
    excerpt = "\n...\n".join(parts)
    if len(excerpt) > MAX_EXCERPT_CHARS:           # keep the end: that is where failures live
        excerpt = "...\n" + excerpt[-MAX_EXCERPT_CHARS:]
    return excerpt


def build_hints(candidates: List[Candidate]) -> str:
    if not candidates:
        return "(no known failure pattern matched)"
    out = []
    for c in candidates[:TOP_CANDIDATES]:
        out.append(f"- {c.category} (score {c.score}, {c.matches} matching lines): {c.label}")
        out.extend(f"    L{e.line_no}: {e.text}" for e in c.evidence)
    return "\n".join(out)


def build_context(ci: str, step: Optional[str], lines: List[str], candidates: List[Candidate]) -> str:
    return (
        f"CI system: {ci}\n"
        f"Failed step or stage: {step or 'not detected'}\n\n"
        f"Rule-based hints (may be wrong):\n{build_hints(candidates)}\n\n"
        f"Log excerpt (cleaned and redacted):\n{build_excerpt(lines, candidates)}"
    )
