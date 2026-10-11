from src.extractor import Trace
from src.formatter import HEADER, format_comment, format_fallback

TRACE = Trace(text="Error: boom\n  at f (src/a.js:3:1)", start=3946, end=4000,
              total_lines=4000, hit_line=3950)


def test_comment_has_header_diagnosis_and_an_honest_footer():
    body = format_comment("**Root cause:** x\n**Suggested fix:** y", TRACE, "some-model")
    assert body.startswith(HEADER)
    assert "**Root cause:** x" in body
    assert "55 of 4,000 log lines around the failure" in body
    assert "some-model" in body
    assert "AI-generated" in body


def test_fallback_shows_the_trace_in_a_collapsed_block():
    body = format_fallback(TRACE, "LLM call failed: timeout")
    assert "LLM call failed: timeout" in body
    assert "<details>" in body and "Error: boom" in body
    assert "55 of 4,000 log lines around the failure" in body


def test_fallback_fence_is_longer_than_any_backticks_in_the_log():
    trace = Trace(text="before\n```\ninside\n```\nafter", start=1, end=5, total_lines=5, hit_line=None)
    body = format_fallback(trace, "x")
    assert "````\nbefore" in body  # a 4-backtick fence cannot be closed by a 3-backtick line


def test_fallback_keeps_the_end_of_an_oversized_trace():
    trace = Trace(text="first\n" + "x" * 9000 + "\nlast-line", start=1, end=3, total_lines=3, hit_line=None)
    body = format_fallback(trace, "x")
    assert "last-line" in body and "first" not in body
    assert len(body) < 7000


def test_fallback_for_an_empty_log():
    empty = Trace(text="", start=0, end=0, total_lines=0, hit_line=None)
    assert "log was empty" in format_fallback(empty, "empty log")
