from src.cleaner import clean_log
from src.extractor import Location, extract_trace, find_locations
from tests.conftest import long_log


def numbered(n, special=None):
    """n filler lines, with `special` {index: text} replacing some of them."""
    special = special or {}
    return [special.get(i, f"filler line {i}") for i in range(n)]


def test_anchors_on_the_real_error_in_the_sample_log(sample_log):
    trace = extract_trace(clean_log(sample_log))
    anchor_text = trace.text.splitlines()[trace.hit_line - trace.start]
    assert anchor_text.strip().startswith("TypeError: Reduce of empty array")


def test_last_error_wins_over_earlier_ones():
    lines = numbered(200, {20: "Error: early warning", 150: "Error: the real failure"})
    trace = extract_trace("\n".join(lines))
    assert trace.hit_line == 151
    assert "the real failure" in trace.text
    assert "early warning" not in trace.text


def test_default_window_is_55_lines():
    lines = numbered(300, {200: "Error: boom"})
    trace = extract_trace("\n".join(lines))
    assert trace.lines_sent == 55
    assert (trace.start, trace.end) == (161, 215)  # 40 before, the error, 14 after


def test_window_is_clipped_at_the_start_of_the_log():
    trace = extract_trace("\n".join(numbered(30, {5: "Error: boom"})))
    assert trace.start == 1


def test_footer_lines_do_not_steal_the_anchor():
    lines = numbered(120, {100: "Error: real failure"})
    lines[101:106] = ["npm ERR! code ELIFECYCLE", "npm ERR! errno 1", "npm ERR! Test failed.",
                      "npm error A complete log of this run can be found in: x", "npm notice done"]
    trace = extract_trace("\n".join(lines))
    assert trace.hit_line == 101


def test_only_footer_lines_still_give_an_anchor():
    trace = extract_trace("ok\nok\nnpm ERR! Test failed.\nok")
    assert trace.hit_line == 3


def test_no_error_words_falls_back_to_the_tail():
    trace = extract_trace("\n".join(numbered(200)))
    assert trace.hit_line is None
    assert trace.lines_sent == 55 and trace.end == 200


def test_empty_log():
    trace = extract_trace("")
    assert trace.text == "" and trace.lines_sent == 0 and trace.fraction == 0.0


def test_very_long_lines_are_truncated():
    trace = extract_trace("Error: " + "x" * 5000)
    assert len(trace.text) < 450


def test_a_4000_line_log_sends_about_one_percent():
    trace = extract_trace(clean_log(long_log(4000)))
    assert trace.total_lines == 4000
    assert trace.lines_sent <= 56
    assert trace.fraction < 0.02


# --- find_locations --------------------------------------------------------

def test_locations_in_the_sample_log_most_likely_first(sample_log):
    locations = find_locations(extract_trace(clean_log(sample_log)).text)
    assert locations == [Location("src/cart.js", 42), Location("test/checkout.test.js", 29)]


def test_dependency_frames_are_skipped():
    text = "at Module._compile (node_modules/jest/lib/x.js:10:5)\nat run (src/app.js:7:1)"
    assert find_locations(text) == [Location("src/app.js", 7)]


def test_duplicates_are_dropped():
    assert find_locations("src/a.js:3:1\nsrc/a.js:3:9") == [Location("src/a.js", 3)]


def test_python_traceback_puts_the_last_frame_first():
    text = (
        "Traceback (most recent call last):\n"
        '  File "/home/runner/work/app/app/main.py", line 10, in <module>\n'
        "    run()\n"
        '  File "/home/runner/work/app/app/src/cart.py", line 42, in apply\n'
        '    raise ValueError("boom")\n'
        "ValueError: boom\n"
    )
    assert find_locations(text, workspace="/home/runner/work/app/app") == [
        Location("src/cart.py", 42),
        Location("main.py", 10),
    ]


def test_absolute_paths_become_repo_relative_with_a_workspace():
    text = "at f (/home/runner/work/shop/shop/src/cart.js:42:26)"
    assert find_locations(text, workspace="/home/runner/work/shop/shop") == [Location("src/cart.js", 42)]


def test_java_style_frames():
    assert find_locations("at com.shop.Cart.apply(Cart.java:42)") == [Location("Cart.java", 42)]


def test_compiler_style_locations():
    assert find_locations("src/main.rs:12:5: error: expected `;`") == [Location("src/main.rs", 12)]


def test_no_locations():
    assert find_locations("Error: something vague happened") == []
