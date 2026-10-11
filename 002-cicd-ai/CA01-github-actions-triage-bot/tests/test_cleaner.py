from src.cleaner import clean_log, collapse_carriage_returns, strip_ansi


def test_strips_color_codes():
    assert strip_ansi("\x1b[31mError\x1b[0m: boom") == "Error: boom"


def test_strips_cursor_and_hyperlink_sequences():
    link = "\x1b]8;;https://example.com\x1b\\docs\x1b]8;;\x1b\\"
    assert strip_ansi("\x1b[2K\x1b[1Gdone " + link) == "done docs"


def test_progress_bar_keeps_only_the_final_state():
    assert collapse_carriage_returns("10%\r55%\r100%\nnext") == "100%\nnext"


def test_crlf_line_endings_are_not_mistaken_for_overwrites():
    assert collapse_carriage_returns("one\r\ntwo\r\n") == "one\ntwo\n"


def test_other_control_characters_go_but_tabs_stay():
    assert clean_log("a\x00b\x07c\td") == "abc\td"


def test_secrets_are_redacted_during_cleaning():
    token = "ghp_" + "A1b2" * 9
    cleaned = clean_log(f"\x1b[33mGITHUB_TOKEN={token}\x1b[0m")
    assert token not in cleaned
    assert "REDACTED" in cleaned


def test_sample_log_is_plain_text_afterwards(sample_log):
    assert "\x1b" in sample_log  # the captured log really is colored
    cleaned = clean_log(sample_log)
    assert "\x1b" not in cleaned and "[31m" not in cleaned


def test_file_line_reference_survives_color_codes(sample_log):
    # In the raw log the colors split the reference: src/cart.js<esc>[2m:42:26
    assert "src/cart.js:42:26" not in sample_log
    assert "src/cart.js:42:26" in clean_log(sample_log)
