"""Deterministic redaction of secrets/PII before anything reaches the LLM.

This is intentionally simple, regex-based redaction for a learning project.
See README.md "Production Considerations" for what a production-grade
redaction layer should actually look like (dedicated secret scanners,
DLP tooling, etc.). None of this logic is AI-driven on purpose — redaction
must be reliable and auditable, not probabilistic.
"""

import re

_PATTERNS = [
    # Bearer / Authorization tokens
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-_\.]{10,}"), r"\1[REDACTED_TOKEN]"),
    # api_key = "..." / api-key: ...
    (re.compile(r"(?i)(api[_-]?key\s*[=:]\s*)[\"']?[A-Za-z0-9\-_]{10,}[\"']?"), r"\1[REDACTED_API_KEY]"),
    # Connection strings: scheme://user:password@host
    (re.compile(r"(?i)(\w+://)([^:/\s]+):([^@/\s]+)@"), r"\1\2:[REDACTED_PASSWORD]@"),
    # AWS-style access keys
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
    # secret = "..." (generic, catches many app-level secrets)
    (re.compile(r"(?i)(secret\s*[=:]\s*)[\"']?[A-Za-z0-9\-_/+=]{16,}[\"']?"), r"\1[REDACTED_SECRET]"),
    # Email addresses (basic PII)
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[REDACTED_EMAIL]"),
]


def redact(text: str) -> str:
    """Strip common secret/PII patterns from a block of text.

    Runs before any data leaves the cluster boundary toward the LLM API.
    """
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
