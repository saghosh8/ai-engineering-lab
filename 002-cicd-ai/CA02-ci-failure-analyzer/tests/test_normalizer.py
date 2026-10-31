from src.normalizer import collapse_carriage_returns, normalize, strip_ansi


def test_strips_ansi_colors():
    assert strip_ansi("\x1b[31mError\x1b[0m: boom") == "Error: boom"


def test_progress_bar_keeps_final_state():
    assert collapse_carriage_returns("10%\r55%\r100%\ndone") == "100%\ndone"


def test_crlf_is_not_an_overwrite():
    assert collapse_carriage_returns("a\r\nb") == "a\nb"


def test_github_timestamp_removed():
    _, lines = normalize("2026-10-30T09:15:02.1234567Z ##[error]Process completed with exit code 1.")
    assert lines == ["##[error]Process completed with exit code 1."]


def test_gh_cli_job_and_step_prefix_removed():
    raw = "build\tRun npm test\t2026-10-30T09:15:02.1234567Z npm ERR! code E404"
    _, lines = normalize(raw)
    assert lines == ["npm ERR! code E404"]


def test_jenkins_timestamp_removed():
    _, lines = normalize("[2026-10-30T09:15:02.123Z] ERROR: script returned exit code 1")
    assert lines == ["ERROR: script returned exit code 1"]


def test_secrets_are_redacted():
    text, _ = normalize("export TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in text


def test_trailing_blank_lines_dropped_and_empty_log():
    _, lines = normalize("one\ntwo\n\n\n")
    assert lines == ["one", "two"]
    assert normalize("") == ("", [])
