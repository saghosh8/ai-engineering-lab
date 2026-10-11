"""Turns the diagnosis (or the lack of one) into the PR comment body."""

import re

from src.extractor import Trace

HEADER = "### 🤖 CI Triage Bot"
MAX_FALLBACK_CHARS = 6000  # GitHub allows ~65k per comment; stay far below


def format_comment(diagnosis: str, trace: Trace, model: str) -> str:
    """The normal comment: the diagnosis plus an honest footer about what
    the model actually saw."""
    footer = (
        f"<sub>AI-generated from {trace.lines_sent} of {trace.total_lines:,} log "
        f"lines around the failure ({model}). It is a hint, not a verdict — "
        f"check it before acting on it.</sub>"
    )
    return f"{HEADER}\n\n{diagnosis}\n\n---\n{footer}\n"


def _fence_for(text: str) -> str:
    """A code fence longer than any run of backticks inside the text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def format_fallback(trace: Trace, reason: str) -> str:
    """When the model call fails, the bot still saves the reader a scroll:
    it posts the extracted lines around the failure instead of a diagnosis.

    `reason` is shown publicly, so keep it short and generic."""
    if not trace.text:
        return f"{HEADER}\n\nThe build failed, but the log was empty, so there is nothing to show.\n"

    shown = trace.text[-MAX_FALLBACK_CHARS:]
    fence = _fence_for(shown)
    return (
        f"{HEADER}\n\n"
        f"I could not produce a diagnosis ({reason}). Here are the log lines "
        f"around the failure, so you do not have to scroll for them:\n\n"
        f"<details>\n"
        f"<summary>{trace.lines_sent} of {trace.total_lines:,} log lines around the failure</summary>\n\n"
        f"{fence}\n{shown}\n{fence}\n\n"
        f"</details>\n"
    )
