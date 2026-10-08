"""Cheap hallucination check on the model's cited evidence.

Every evidence string the model cites should be traceable to the input we
actually sent (facts + logs). Citations that are not are *flagged*, never
silently dropped, so the engineer can see what happened.

This is a heuristic, not proof: it catches invented log lines and made-up
values, not wrong reasoning from real evidence.
"""

import json
import re
from typing import Any, List

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[:=,\"'\[\]{}()]")  # "exit_code: 1" == "exit_code=1" == {"exit_code": 1}
_TOKEN = re.compile(r"[a-z0-9_.:/\-]{3,}")


def _flatten(value: Any) -> str:
    """Render nested data as plain text (no JSON escaping/quoting noise)."""
    if isinstance(value, dict):
        return " ".join(f"{k} {_flatten(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def _normalize(text: str) -> str:
    return _WS.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


def is_grounded(claim: str, source_text: str, threshold: float = 0.8) -> bool:
    """True if the claim appears in the source verbatim (modulo case and
    whitespace), or if at least `threshold` of its meaningful tokens do —
    models often lightly paraphrase a log line rather than copy it.
    """
    claim_n, source_n = _normalize(claim), _normalize(source_text)
    if not claim_n:
        return False
    if claim_n in source_n:
        return True
    tokens = _TOKEN.findall(claim_n)
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in source_n)
    return hits / len(tokens) >= threshold


def find_unverified(evidence_items: List[str], *sources: Any) -> List[str]:
    """Return the cited items that cannot be traced to any source."""
    source_text = " ".join(_flatten(s) for s in sources)
    return [e for e in evidence_items if not is_grounded(e, source_text)]
