"""Deterministic redaction of secrets before a log excerpt leaves the runner.

Regex-based on purpose: redaction must be reliable and auditable, not
probabilistic. GitHub Actions already masks values registered as secrets
(they show up as ***), so this is a second layer for tokens that were
never registered: a `set -x` trace, an `env` dump, a connection string
printed by a failing test.

It is a safety net, not a guarantee — see "Known limitations" in the
README. Extend the patterns for your own token formats and internal
hostnames before pointing this at a private repository.

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
    # GitHub tokens: classic (ghp_, gho_, ghu_, ghs_, ghr_) and fine-grained
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
     "[REDACTED_GITHUB_TOKEN]"),
    # Provider API keys that look like sk-... (Anthropic, OpenAI and friends)
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "[REDACTED_API_KEY]"),
    # Slack tokens
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "[REDACTED_SLACK_TOKEN]"),
    # AWS access key IDs (long-term and temporary)
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    # key=value / key: value / "key": "value" where the key looks sensitive
    (re.compile(rf"(?i)({_SENSITIVE_KEY}[\"']?\s*[=:]\s*){_VALUE}"), r"\1[REDACTED]"),
    # Email addresses (basic PII)
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[REDACTED_EMAIL]"),
]


def redact(text: str) -> str:
    """Strip common secret/PII patterns from a block of text.

    Runs before any log text is sent to the LLM API or posted to a PR.
    """
    if not text:
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
