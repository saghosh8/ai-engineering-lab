from src.extractor import Location
from src.triage import triage_log
from tests.conftest import GOOD_DIAGNOSIS, FakeClient, long_log


def test_happy_path_on_the_sample_log(sample_log):
    result = triage_log(sample_log, client=FakeClient())
    assert result.succeeded and result.error is None
    assert result.diagnosis == GOOD_DIAGNOSIS
    assert GOOD_DIAGNOSIS in result.comment
    assert result.locations[0] == Location("src/cart.js", 42)


def test_the_model_sees_clean_text_not_color_codes(sample_log):
    client = FakeClient()
    triage_log(sample_log, client=client)
    assert "\x1b" not in client.prompt
    assert "Reduce of empty array with no initial value" in client.prompt


def test_secrets_never_reach_the_model_or_the_comment():
    token = "ghp_" + "A1b2" * 9
    raw = f"GITHUB_TOKEN={token}\nError: boom\n"
    client = FakeClient()
    result = triage_log(raw, client=client)
    assert token not in client.prompt
    assert token not in result.comment


def test_a_4000_line_log_sends_about_one_percent_to_the_model():
    client = FakeClient()
    result = triage_log(long_log(4000), client=client)
    sent_lines = client.prompt.count("\n")
    assert result.trace.total_lines == 4000
    assert result.trace.fraction < 0.02
    assert sent_lines < 80  # the prompt is the trace plus a few framing lines
    assert "log lines around the failure" in result.comment and "4,000" in result.comment


def test_unusable_model_reply_falls_back_to_the_raw_trace(sample_log):
    result = triage_log(sample_log, client=FakeClient("I cannot help with that."))
    assert not result.succeeded and "unusable" in result.error
    assert "<details>" in result.comment and "TypeError" in result.comment


def test_api_failure_never_raises_and_still_posts_something_useful(sample_log):
    result = triage_log(sample_log, client=FakeClient(raises=TimeoutError("timed out")))
    assert not result.succeeded and "TimeoutError" in result.error
    assert "TypeError" in result.comment


def test_the_public_comment_does_not_echo_raw_api_error_details(sample_log):
    secret_detail = "internal request id req_123 and account details"
    result = triage_log(sample_log, client=FakeClient(raises=RuntimeError(secret_detail)))
    assert secret_detail in result.error          # kept for the step log
    assert secret_detail not in result.comment    # but never posted on the PR
    assert "the model call failed: RuntimeError" in result.comment


def test_fallback_comment_is_redacted_too():
    token = "ghp_" + "A1b2" * 9
    result = triage_log(f"token={token}\nError: boom\n", client=FakeClient(raises=RuntimeError("x")))
    assert token not in result.comment


def test_empty_log():
    result = triage_log("", client=FakeClient())
    assert not result.succeeded and "empty" in result.comment
