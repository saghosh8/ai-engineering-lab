import pytest

from src.extractor import Location
from src.github_client import (
    GitHubError,
    choose_location,
    fetch_changed_lines,
    parse_patch,
    post_comment,
)
from tests.conftest import FakeGh, field

CART = "app/src/cart.js"
PATCH = (
    "@@ -38,7 +38,9 @@ function total(items) {\n"
    " }\n"
    " \n"
    " function applyDiscount(cart) {\n"
    "   const { items } = cart;\n"
    "-  return total(items) * 0.9;\n"
    "+  const cheapest = items.reduce((a, b) => a);\n"
    "+  const subtotal = total(items);\n"
    "+  return subtotal * 0.9;\n"
    " }\n"
    " \n"
    " module.exports = {};\n"
)
BODY = "### 🤖 CI Triage Bot\n\n**Root cause:** x"


# --- parse_patch -----------------------------------------------------------

def test_parse_patch_numbers_new_side_lines():
    assert parse_patch(PATCH) == set(range(38, 48))


def test_parse_patch_with_several_hunks_and_no_newline_marker():
    patch = (
        "@@ -1,2 +1,2 @@\n a\n-b\n+c\n"
        "@@ -50,2 +50,3 @@\n x\n+y\n z\n"
        "\\ No newline at end of file\n"
    )
    assert parse_patch(patch) == {1, 2, 50, 51, 52}


def test_parse_patch_of_a_binary_or_empty_diff():
    assert parse_patch("") == set()


# --- choose_location -------------------------------------------------------

def test_choose_location_matches_by_path_suffix_and_returns_the_repo_path():
    changed = {CART: set(range(38, 48))}
    assert choose_location([Location("src/cart.js", 42)], changed) == Location(CART, 42)


def test_choose_location_skips_lines_outside_the_diff_and_takes_the_next():
    changed = {CART: {41, 42, 43}}
    candidates = [Location("src/cart.js", 99), Location("src/cart.js", 42)]
    assert choose_location(candidates, changed) == Location(CART, 42)


def test_choose_location_does_not_match_a_longer_file_name():
    assert choose_location([Location("cart.js", 1)], {"app/src/shopping-cart.js": {1}}) is None


def test_choose_location_none_when_nothing_matches():
    assert choose_location([Location("test/checkout.test.js", 29)], {CART: {42}}) is None


# --- fetch_changed_lines ---------------------------------------------------

def test_fetch_changed_lines_reads_every_file():
    gh = FakeGh(changed={CART: PATCH, "README.md": "@@ -1 +1,2 @@\n a\n+b\n"})
    changed = fetch_changed_lines("o/r", 7, gh)
    assert changed[CART] == set(range(38, 48))
    assert changed["README.md"] == {1, 2}


def test_fetch_changed_lines_accepts_quoted_json_lines():
    """Plain `jq` (unlike `gh --jq`) prints the @json string with quotes."""
    import json
    import subprocess

    quoted = json.dumps(json.dumps([CART, PATCH]))
    runner = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, quoted + "\n", "")
    assert fetch_changed_lines("o/r", 7, runner)[CART] == set(range(38, 48))


# --- post_comment ----------------------------------------------------------

def test_posts_inline_when_a_trace_line_is_in_the_diff():
    gh = FakeGh(changed={CART: PATCH})
    outcome = post_comment("o/r", 7, "abc1234", BODY, [Location("src/cart.js", 42)], gh)
    assert outcome.kind == "inline" and outcome.location == Location(CART, 42)
    assert gh.kinds == ["files", "inline"]
    inline = gh.calls[-1]
    assert field(inline, "path") == CART
    assert field(inline, "line") == "42"
    assert field(inline, "commit_id") == "abc1234"
    assert field(inline, "side") == "RIGHT"
    assert field(inline, "body") == BODY


def test_falls_back_to_a_pr_comment_when_the_line_is_not_in_the_diff():
    gh = FakeGh(changed={CART: PATCH})
    outcome = post_comment("o/r", 7, "abc1234", BODY, [Location("test/checkout.test.js", 29)], gh)
    assert outcome.kind == "pr" and "diff" in outcome.note
    assert gh.kinds == ["files", "pr"]


def test_falls_back_when_github_refuses_the_inline_comment():
    gh = FakeGh(changed={CART: PATCH}, fail_inline=True)
    outcome = post_comment("o/r", 7, "abc1234", BODY, [Location("src/cart.js", 42)], gh)
    assert outcome.kind == "pr" and "refused" in outcome.note
    assert gh.kinds == ["files", "inline", "pr"]


def test_falls_back_when_the_diff_cannot_be_read():
    gh = FakeGh(fail_files=True)
    outcome = post_comment("o/r", 7, "abc1234", BODY, [Location("src/cart.js", 42)], gh)
    assert outcome.kind == "pr" and "diff" in outcome.note
    assert gh.kinds == ["files", "pr"]


def test_no_locations_means_no_diff_lookup():
    gh = FakeGh()
    outcome = post_comment("o/r", 7, "abc1234", BODY, [], gh)
    assert outcome.kind == "pr" and "no file:line" in outcome.note
    assert gh.kinds == ["pr"]


def test_pr_comment_goes_to_the_issues_endpoint_with_the_body():
    gh = FakeGh()
    post_comment("o/r", 7, "abc1234", BODY, [], gh)
    assert "repos/o/r/issues/7/comments" in gh.calls[0]
    assert field(gh.calls[0], "body") == BODY


def test_failure_to_post_anywhere_raises():
    with pytest.raises(GitHubError, match="403"):
        post_comment("o/r", 7, "abc1234", BODY, [], FakeGh(fail_pr=True))


def test_gh_is_always_called_with_an_argument_list():
    gh = FakeGh(changed={CART: PATCH})
    post_comment("o/r", 7, "abc1234", "body with $(rm -rf /) and `backticks`", [Location("src/cart.js", 42)], gh)
    assert all(cmd[0] == "gh" for cmd in gh.calls)
    assert field(gh.calls[-1], "body") == "body with $(rm -rf /) and `backticks`"
