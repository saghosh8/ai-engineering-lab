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
import re
import sys
from typing import Literal

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

SYSTEM_PROMPT = """You are a Kubernetes troubleshooting assistant.
You are given evidence from a single pod. Analyse it and return hypotheses
ranked by likelihood.

Rules:
- Only cite evidence present in the input. Never invent log lines or field values.
- If the evidence is insufficient, say so and set confidence to "low".
- Suggested commands must be read-only (get, describe, logs, top).

Return ONLY valid JSON matching this schema:
{"summary": str,
 "hypotheses": [{"cause": str, "confidence": "high|medium|low",
                 "evidence": [str], "next_steps": [str]}],
 "missing_information": [str]}"""


class Hypothesis(BaseModel):
    cause: str
    confidence: Literal["high", "medium", "low"]
    evidence: list[str]
    next_steps: list[str]


class Analysis(BaseModel):
    summary: str
    hypotheses: list[Hypothesis]
    missing_information: list[str]


def _strip_code_fences(text: str) -> str:
    """The model sometimes wraps JSON in ```json ... ``` even when told
    not to. Strip fences defensively before parsing.
    """
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())


def call_llm(evidence: dict, client: Anthropic | None = None) -> Analysis:
    """Send the evidence bundle to the model and return a validated
    Analysis object. Exits with a clear message on malformed output
    rather than rendering a half-parsed result.
    """
    client = client or Anthropic()

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(evidence, indent=2)}],
    )

    raw_text = resp.content[0].text

    try:
        analysis = Analysis.model_validate_json(_strip_code_fences(raw_text))
    except ValidationError:
        with open("./evidence.json", "w") as f:
            json.dump(evidence, f, indent=2)
        sys.exit(
            "Model returned malformed output. Raw evidence saved to ./evidence.json"
        )

    return analysis


def verify_evidence_grounding(analysis: Analysis, evidence: dict) -> Analysis:
    """Cheap hallucination check: every evidence string a hypothesis
    cites should appear (as a substring) somewhere in the evidence
    bundle we actually sent. Hypotheses that fail are flagged, not
    silently dropped, so the engineer can see what happened.
    """
    haystack = json.dumps(evidence).lower()

    for hyp in analysis.hypotheses:
        for claim in hyp.evidence:
            if claim.lower()[:40] not in haystack:
                hyp.cause = f"[UNVERIFIED CITATION] {hyp.cause}"
                break

    return analysis
