"""The single LLM call in this project.

One-shot: structured facts + redacted log excerpt in, a schema-validated
Diagnosis out. No agent loop, no tool calling, no RAG — see the article's
"Engineering Decisions" section for why none of that is needed here.
"""

import json
import os
from typing import Any, Dict

from anthropic import Anthropic

from src.grounding import find_unverified
from src.models import Diagnosis

DEFAULT_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a Kubernetes troubleshooting assistant.
You will be given deterministic, ground-truth facts about a crashed pod
and a redacted excerpt of its logs. Your job is to propose the single
most likely root cause, grounded only in the evidence provided.

Rules:
- Never state something as fact unless it's directly supported by the facts or logs given.
- Quote evidence verbatim from the facts or logs; do not paraphrase or invent log lines.
- If the evidence is ambiguous or incomplete, say so and lower your confidence.
- The recommended next step must be read-only (get, describe, logs, top).
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


class LLMOutputError(Exception):
    """The model's response could not be turned into a valid Diagnosis."""


def build_prompt(facts: Dict[str, Any], log_excerpt: str) -> str:
    return f"""Facts (ground truth, extracted deterministically from the Kubernetes API):
{json.dumps(facts, indent=2)}

Log excerpt (last lines, redacted):
{log_excerpt}

{RESPONSE_SCHEMA_HINT}
"""


def extract_json(text: str) -> str:
    """Return the outermost {...} object in the text.

    Handles markdown fences and stray preamble/postamble without any
    fence-specific string surgery.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise LLMOutputError("no JSON object found in model response")
    return text[start : end + 1]


def diagnose(facts: Dict[str, Any], log_excerpt: str, model: str | None = None,
             max_tokens: int = 800, client: Anthropic | None = None) -> Diagnosis:
    """Call the LLM once and return a validated, grounding-checked Diagnosis.

    Raises LLMOutputError (or pydantic.ValidationError) if the response is
    truncated, empty or doesn't match the schema — callers catch this and
    fall back to showing raw evidence (see troubleshooter.py).
    """
    client = client or Anthropic()  # reads ANTHROPIC_API_KEY from environment
    # Read at call time: the CLI calls load_dotenv() *after* this module is
    # imported, so a module-level os.environ lookup would miss .env values.
    model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_prompt(facts, log_excerpt)}],
    )

    if response.stop_reason == "max_tokens":
        raise LLMOutputError("model response was truncated (max_tokens reached)")
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    if not text.strip():
        raise LLMOutputError("model returned no text")

    diagnosis = Diagnosis.model_validate_json(extract_json(text))
    diagnosis.unverified_evidence = find_unverified(diagnosis.evidence, facts, log_excerpt)
    return diagnosis
