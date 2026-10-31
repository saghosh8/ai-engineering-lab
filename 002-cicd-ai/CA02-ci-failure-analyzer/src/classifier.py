"""Step 3: rank the likely failure categories, with evidence.

For every signature in the catalog we collect the log lines that match
it. A category's score is:

    score = weight                      how specific a root cause it is
          + min(matches, 5) * 0.4       more matching lines, more likely
          + position * 2                0 at the top of the log, 2 at the end

The position bonus is there because the real cause is usually close to
the end of a failed log. Nothing here is probabilistic: the same log
always gives the same ranking, and every score can be explained by the
lines in `evidence`.
"""

from dataclasses import dataclass, field
from typing import List

from src.signatures import SIGNATURES

MAX_EVIDENCE = 3          # matching lines kept per category (the last ones)
MAX_LINE_CHARS = 240      # long lines are cut so one line cannot flood the prompt


@dataclass
class Evidence:
    line_no: int          # 1-based, in the normalized log
    text: str


@dataclass
class Candidate:
    category: str
    label: str
    hint: str
    score: float
    matches: int
    evidence: List[Evidence] = field(default_factory=list)


def classify(lines: List[str]) -> List[Candidate]:
    """All categories with at least one matching line, best first."""
    total = max(len(lines), 1)
    found: List[Candidate] = []
    for sig in SIGNATURES:
        hits = [i for i, line in enumerate(lines)
                if any(p.search(line) for p in sig.patterns)]
        if not hits:
            continue
        score = sig.weight + min(len(hits), 5) * 0.4 + (hits[-1] / total) * 2
        evidence = [Evidence(i + 1, lines[i].strip()[:MAX_LINE_CHARS]) for i in hits[-MAX_EVIDENCE:]]
        found.append(Candidate(sig.category, sig.label, sig.hint, round(score, 2), len(hits), evidence))
    found.sort(key=lambda c: c.score, reverse=True)
    return found
