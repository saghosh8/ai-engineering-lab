"""The single LLM call in this project.

One-shot: structured facts + redacted log excerpt in, a schema-validated
Diagnosis out. No agent loop, no tool calling, no RAG — see the article's
"Engineering Decisions" section for why none of that is needed here.
"""

import json
import os
from typing import Any, Dict

from anthropic import Anthropic

from src.models import Diagnosis

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

SYSTEM_PROMPT = """You are a Kubernetes troubleshooting assistant.
You will be given deterministic, ground-truth facts about a crashed pod
and a redacted excerpt of its logs. Your job is to propose the single
most likely root cause, grounded only in the evidence provided.

Rules:
- Never state something as fact unless it's directly supported by the facts or logs given.
- If the evidence is ambiguous or incomplete, say so and lower your confidence.
- Return ONLY valid JSON. No preamble, no markdown fences, no commentary.
"""

RESPONSE_SCHEMA_HINT = """
Return JSON matching exactly this shape:
{
  "likely_cause": "<plain-language hypothesis>",
  "evidence": ["<specific fact or log line supporting the hypothesis>", "..."],
  "confidence": "low" | "medium" | "high",
  "recommended_next_step": "<one concrete, verifiable action>"
}
"""


def build_prompt(facts: Dict[str, Any], log_excerpt: str) -> str:
    return f"""Facts (ground truth, extracted deterministically from the Kubernetes API):
{json.dumps(facts, indent=2)}

Log excerpt (last lines, redacted):
{log_excerpt}

{RESPONSE_SCHEMA_HINT}
"""


def diagnose(facts: Dict[str, Any], log_excerpt: str, model: str = DEFAULT_MODEL,
             max_tokens: int = 500) -> Diagnosis:
    """Call the LLM once and return a validated Diagnosis.

    Raises pydantic.ValidationError if the model's response doesn't match
    the expected schema — callers should catch this and fall back to
    showing raw evidence (see troubleshooter.py).
    """
    client = Anthropic()  # reads ANTHROPIC_API_KEY from environment
    prompt = build_prompt(facts, log_excerpt)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()
    # Defensive: strip markdown fences in case the model adds them anyway
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()

    return Diagnosis.model_validate_json(raw_text)
