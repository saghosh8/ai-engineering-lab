"""Orchestrates the pipeline: clean -> extract -> diagnose -> format.

Posting is a separate step (src/github_client.py) so this module can be
exercised without GitHub, and the CLI (src/cli.py) and the demo script
(examples/demo.py) both call into it.
"""

from dataclasses import dataclass
from typing import List, Optional

from anthropic import Anthropic

from src.cleaner import clean_log
from src.extractor import Location, Trace, extract_trace, find_locations
from src.formatter import format_comment, format_fallback
from src.llm_client import LLMOutputError, diagnose, resolve_model


@dataclass
class TriageResult:
    """Either a diagnosis or a fallback with the reason, so the caller
    always has a comment worth posting."""

    comment: str
    trace: Trace
    locations: List[Location]
    diagnosis: Optional[str] = None
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.diagnosis is not None


def triage_log(raw_log: str, *, before: int = 40, after: int = 15,
               workspace: Optional[str] = None, model: Optional[str] = None,
               client: Optional[Anthropic] = None) -> TriageResult:
    """Full pipeline for one failed build log."""
    cleaned = clean_log(raw_log)
    trace = extract_trace(cleaned, before=before, after=after)
    locations = find_locations(trace.text, workspace=workspace)

    if not trace.text:
        return TriageResult(format_fallback(trace, "empty log"), trace, locations,
                            error="empty log")

    # `error` is the full detail for the step log; `reason` is the short,
    # generic version that goes into the public PR comment.
    try:
        diagnosis = diagnose(trace.text, model=model, client=client)
    except LLMOutputError as e:
        error, reason = f"model response was unusable: {e}", "the model's reply was unusable"
    except Exception as e:  # network, auth, rate limit: never block the PR on the bot
        error = f"LLM call failed: {type(e).__name__}: {str(e)[:200]}"
        reason = f"the model call failed: {type(e).__name__}"
    else:
        return TriageResult(format_comment(diagnosis, trace, resolve_model(model)),
                            trace, locations, diagnosis=diagnosis)

    return TriageResult(format_fallback(trace, reason), trace, locations, error=error)
