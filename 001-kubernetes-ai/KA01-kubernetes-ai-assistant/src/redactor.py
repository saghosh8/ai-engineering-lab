"""Deterministic redaction of secrets/PII before anything reaches the LLM.

Regex-based on purpose: redaction must be reliable and auditable, not
probabilistic. It is a safety net, not a guarantee — see "Known
limitations" in the README for what a production-grade layer adds
(dedicated secret scanners, DLP tooling, allow-listing log fields).

Patterns run in order; earlier ones may consume text that later ones
would otherwise match (e.g. URL passwords before email addresses).
"""

import re

# A key name that *contains* a sensitive word, e.g. DB_PASSWORD, api-key,
# client_secret, refresh_token. Bare "key" is deliberately NOT included
# (it matches too much: cache_key, KEYCLOAK_URL, ...).
_SENSITIVE_KEY = (
    r"[\w.\-]*(?:password|passwd|pwd|secret|token|credential|"
    r"api[_\-]?key|access[_\-]?key|secret[_\-]?key|private[_\-]?key)[\w.\-]*"
)
# A value: "quoted", 'quoted' or a bare run up to whitespace/delimiter.
_VALUE = r"""(?:"[^"]*"|'[^']*'|[^\s,;&"']+)"""

_PATTERNS = [
    # PEM private key blocks (multi-line)
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
    # Connection strings: scheme://user:password@host
    (re.compile(r"(\w[\w+.\-]*://)([^:/\s@]+):([^@/\s]+)@"), r"\1\2:[REDACTED_PASSWORD]@"),
    # Bearer tokens
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-_.~+/=]{8,}"), r"\1[REDACTED_TOKEN]"),
    # JWTs
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}"),
     "[REDACTED_JWT]"),
    # AWS access key IDs (long-term and temporary)
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    # key=value / key: value / "key": "value" where the key looks sensitive
    (re.compile(rf"(?i)({_SENSITIVE_KEY}[\"']?\s*[=:]\s*){_VALUE}"), r"\1[REDACTED]"),
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
