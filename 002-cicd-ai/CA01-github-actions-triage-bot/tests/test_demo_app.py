"""The README promises a specific demo failure. Keep the demo app, the
captured log and those promises in sync."""

from pathlib import Path

from tests.conftest import ROOT

CART = ROOT / "demo-app" / "src" / "cart.js"


def test_the_bug_sits_on_line_42_of_cart_js():
    line_42 = CART.read_text().splitlines()[41]
    assert ".reduce(" in line_42


def test_the_captured_log_fails_on_that_line(sample_log):
    assert "Reduce of empty array" in sample_log
    assert "src/cart.js" in sample_log and ":42:" in sample_log


def test_the_demo_tests_include_the_empty_cart_case():
    tests = (ROOT / "demo-app" / "test" / "checkout.test.js").read_text()
    assert "applies discount to empty cart" in tests
