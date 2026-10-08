import pytest

from src.redactor import redact


@pytest.mark.parametrize("raw, leaked", [
    ("postgres://admin:hunter2@db.example.com:5432/x", "hunter2"),
    ("password=hunter2", "hunter2"),
    ("DB_PASSWORD=hunter2 failed", "hunter2"),
    ('{"password": "p4ss w0rd"}', "p4ss"),
    ("token: abc123def456ghi789", "abc123def456ghi789"),
    ("secret=short", "short"),
    ("Authorization: Bearer abcdefghij12345", "abcdefghij12345"),
    ("api-key = sk_live_1234567890abcdef", "sk_live_1234567890abcdef"),
    ("aws AKIAABCDEFGHIJKLMNOP", "AKIAABCDEFGHIJKLMNOP"),
    ("jwt eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4", "SflKxwRJSMeKKF2QT4"),
    ("contact bob@example.com", "bob@example.com"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----", "MIIabc"),
])
def test_secrets_are_removed(raw, leaked):
    assert leaked not in redact(raw)


@pytest.mark.parametrize("benign", [
    "password authentication failed for user app",
    "cache_key=abc KEYCLOAK_URL=http://keycloak:8080",
    "connection timed out after 5s",
])
def test_benign_text_untouched(benign):
    assert redact(benign) == benign


def test_idempotent_and_empty():
    once = redact("password=hunter2 bob@example.com")
    assert redact(once) == once
    assert redact("") == ""
