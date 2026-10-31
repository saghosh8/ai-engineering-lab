"""Orchestrates the pipeline: normalize -> detect -> classify -> explain -> verify.

Everything except the explanation is deterministic. If the model is
unavailable (no API key, network error, bad output) the analyzer still
returns the rule-based result, clearly labelled as such.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from src.classifier import Candidate, classify
from src.context import build_context
from src.detector import CI_SYSTEMS, UNKNOWN, detect_ci, find_failed_step
from src.grounding import ground
from src.llm_client import LLMOutputError, diagnose
from src.normalizer import normalize

_FAILURE_MARKERS = [
    re.compile(r"##\[error\]"),
    re.compile(r"^Finished: (?:FAILURE|UNSTABLE|ABORTED)"),
    re.compile(r"(?i)\b(?:exit code|exited with|returned exit code|exit status) [1-9]\d*\b"),
    re.compile(r"^ERROR: "),
]


@dataclass
class AnalysisResult:
    ci: str
    step: Optional[str]
    line_count: int
    failed: bool
    candidates: List[Candidate] = field(default_factory=list)
    diagnosis: Optional[dict] = None
    notes: List[str] = field(default_factory=list)
    llm_used: bool = False
    llm_skipped_reason: Optional[str] = None

    @property
    def category(self) -> str:
        """The headline answer: the model's if it gave one, else the top rule."""
        if self.diagnosis and self.diagnosis["category"] != "unknown":
            return self.diagnosis["category"]
        if self.candidates:
            return self.candidates[0].category
        return "unknown"


def _looks_failed(lines: List[str], candidates: List[Candidate]) -> bool:
    return bool(candidates) or any(m.search(line) for line in lines for m in _FAILURE_MARKERS)


def analyze(raw_log: str, ci: str = "auto", use_llm: bool = True,
            model: Optional[str] = None, client=None) -> AnalysisResult:
    text, lines = normalize(raw_log)
    if ci == "auto" or ci not in CI_SYSTEMS:
        ci = detect_ci(lines)
    candidates = classify(lines)
    failed = _looks_failed(lines, candidates)
    result = AnalysisResult(ci=ci, step=find_failed_step(lines, ci), line_count=len(lines),
                            failed=failed, candidates=candidates)

    if not lines:
        result.failed = False
        result.notes.append("The log is empty.")
        return result
    if not failed:
        result.notes.append("No failure signal found in this log.")
        return result

    if not use_llm:
        result.llm_skipped_reason = "AI step turned off (--no-llm)"
        return result
    if client is None and not os.environ.get("ANTHROPIC_API_KEY"):
        result.llm_skipped_reason = "ANTHROPIC_API_KEY is not set"
        return result

    try:
        diagnosis = diagnose(build_context(ci, result.step, lines, candidates), model=model, client=client)
    except LLMOutputError as exc:
        result.llm_skipped_reason = f"model output rejected: {exc}"
        return result
    except Exception as exc:                      # network, auth, rate limit: never crash the report
        result.llm_skipped_reason = f"model call failed ({type(exc).__name__})"
        return result

    diagnosis, notes = ground(diagnosis, text)
    result.notes.extend(notes)
    if candidates and diagnosis["category"] not in ("unknown", candidates[0].category):
        result.notes.append(
            f"The model chose '{diagnosis['category']}' but the rules ranked '{candidates[0].category}' first. "
            "Check both before acting.")
        if diagnosis["confidence"] == "high":
            diagnosis["confidence"] = "medium"
    result.diagnosis = diagnosis
    result.llm_used = True
    return result
