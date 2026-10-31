"""Step 6: fact-check the model against the log.

The model is asked to copy its evidence lines exactly. We check that each
one really appears in the log it was given. A quote that is not in the
log is dropped, and a diagnosis with no verified evidence can never be
reported with more than "low" confidence. This is the guard against a
confident-sounding hallucination.
"""

import re
from typing import List, Tuple

_WS = re.compile(r"\s+")
_LINE_PREFIX = re.compile(r"^L\d+:\s*")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def ground(diagnosis: dict, log_text: str) -> Tuple[dict, List[str]]:
    """Return (diagnosis with only verified evidence, notes about what changed)."""
    haystack = _norm(log_text)
    notes: List[str] = []
    verified, dropped = [], 0
    for quote in diagnosis.get("evidence", []):
        q = _norm(_LINE_PREFIX.sub("", quote))
        if q and q in haystack:
            verified.append(quote)
        else:
            dropped += 1

    result = dict(diagnosis, evidence=verified)
    if dropped:
        notes.append(f"{dropped} quoted line(s) from the model were not found in the log and were removed.")
    if not verified and result["category"] != "unknown":
        notes.append("No quoted evidence could be verified against the log, so confidence is set to low.")
        result["confidence"] = "low"
    return result, notes
