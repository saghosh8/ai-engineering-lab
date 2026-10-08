"""
analyzer.py

The only AI component in this tool: one call to the Anthropic API,
plus strict validation of what comes back.

The model receives a compact evidence bundle (see context.py) and is
asked to return ranked hypotheses with supporting evidence — never a
confirmed root cause. Every hypothesis must cite evidence that actually
exists in the input, which we verify after the fact.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError

from src.grounding import find_unverified

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a Kubernetes troubleshooting assistant.
You are given evidence from a single pod. Analyse it and return hypotheses
ranked by likelihood.

Rules:
- Only cite evidence present in the input. Never invent log lines or field values.
- Quote evidence verbatim from the input; do not paraphrase.
- If the evidence is insufficient, say so and set confidence to "low".
- Suggested commands must be read-only (get, describe, logs, top).
- "logs_source" tells you whether logs are from the previous (crashed) run or the current one.

Return ONLY valid JSON matching this schema:
{"summary": str,
 "hypotheses": [{"cause": str, "confidence": "high|medium|low",
                 "evidence": [str], "next_steps": [str]}],
 "missing_information": [str]}"""


class AnalysisError(Exception):
    """The model's response could not be turned into a valid Analysis."""


class Hypothesis(BaseModel):
    cause: str
    confidence: Literal["high", "medium", "low"]
    evidence: list[str]
    next_steps: list[str]
    # Filled in by our code (verify_evidence_grounding), never by the model.
    unverified_evidence: list[str] = Field(default_factory=list)


class Analysis(BaseModel):
    summary: str
    hypotheses: list[Hypothesis]
    missing_information: list[str]


def _extract_json(text: str) -> str:
    """Return the outermost {...} object in the text. Handles markdown
    fences and stray preamble/postamble the model sometimes adds even
    when told not to.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise AnalysisError("no JSON object found in model response")
    return text[start : end + 1]


def call_llm(evidence: dict, client: Anthropic | None = None) -> Analysis:
    """Send the evidence bundle to the model and return a validated
    Analysis object.

    Raises AnalysisError on truncated, empty or malformed output rather
    than rendering a half-parsed result. The caller decides what to do
    (the CLI saves the evidence and exits).
    """
    client = client or Anthropic()
    # Read at call time so values loaded from .env after import are honoured.
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(evidence, indent=2)}],
    )

    if resp.stop_reason == "max_tokens":
        raise AnalysisError("model response was truncated (max_tokens reached)")
    raw_text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if not raw_text.strip():
        raise AnalysisError("model returned no text")

    try:
        return Analysis.model_validate_json(_extract_json(raw_text))
    except ValidationError as e:
        raise AnalysisError(f"model output did not match the schema: {e}") from e


def verify_evidence_grounding(analysis: Analysis, evidence: dict) -> Analysis:
    """Cheap hallucination check: every evidence string a hypothesis
    cites should be traceable to the evidence bundle we actually sent
    (see grounding.py). Failures are flagged on the hypothesis, not
    silently dropped, so the engineer can see what happened.
    """
    for hyp in analysis.hypotheses:
        hyp.unverified_evidence = find_unverified(hyp.evidence, evidence)
        if hyp.unverified_evidence and not hyp.cause.startswith("[UNVERIFIED CITATION]"):
            hyp.cause = f"[UNVERIFIED CITATION] {hyp.cause}"

    return analysis
