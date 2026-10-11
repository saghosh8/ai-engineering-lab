import pytest

from src.redactor import redact

# Fake credentials are assembled at runtime so no real-looking token is
# ever committed to the repository.
GITHUB_TOKEN = "ghp_" + "A1b2" * 9
FINE_GRAINED = "github_pat_" + "Z9y8" * 6
API_KEY = "sk-" + "ant-" + "k3Y9" * 6
AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


@pytest.mark.parametrize("secret", [GITHUB_TOKEN, FINE_GRAINED, API_KEY, AWS_KEY])
def test_token_formats_are_removed(secret):
    assert secret not in redact(f"using credentials {secret} for the request")


def test_key_value_secrets():
    out = redact("DB_PASSWORD=hunter2hunter2 and api_key: 'abc123def456'")
    assert "hunter2hunter2" not in out and "abc123def456" not in out


def test_json_style_secret():
    assert "s3cr3t-value" not in redact('{"client_secret": "s3cr3t-value"}')


def test_bearer_token():
    out = redact("Authorization: Bearer abcdef1234567890")
    assert "abcdef1234567890" not in out and "Bearer" in out


def test_url_credentials():
    out = redact("connecting to postgres://app:p4ssw0rd@db-primary:5432/shop")
    assert "p4ssw0rd" not in out and "db-primary" in out


def test_private_key_block():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"
    assert "MIIabc" not in redact(pem)


def test_email_addresses():
    assert "maya@example.com" not in redact("committer maya@example.com failed")


@pytest.mark.parametrize("line", [
    "Expected: 0",
    "Received: undefined",
    "at reduce (src/cart.js:42:26)",
    "cache_key=abc123",
    "TypeError: Reduce of empty array with no initial value",
])
def test_ordinary_log_lines_are_untouched(line):
    assert redact(line) == line


def test_empty_input():
    assert redact("") == ""
