from src.grounding import ground

LOG = "npm error code E404\nnpm error 404 Not Found - GET https://registry.npmjs.org/@acme%2fui-kit"


def d(**kw):
    base = {"category": "dependency_install", "likely_cause": "x", "evidence": [], "confidence": "high",
            "flaky_suspected": False, "next_steps": []}
    base.update(kw)
    return base


def test_verified_quote_is_kept_and_confidence_unchanged():
    out, notes = ground(d(evidence=["npm error code E404"]), LOG)
    assert out["evidence"] == ["npm error code E404"] and out["confidence"] == "high" and notes == []


def test_whitespace_and_case_do_not_matter_and_line_prefix_is_ignored():
    out, _ = ground(d(evidence=["L2:  NPM ERROR 404   not found"]), LOG)
    assert len(out["evidence"]) == 1


def test_invented_quote_is_dropped():
    out, notes = ground(d(evidence=["npm error code E404", "segfault in libfoo"]), LOG)
    assert out["evidence"] == ["npm error code E404"] and "removed" in notes[0]


def test_no_verified_evidence_forces_low_confidence():
    out, notes = ground(d(evidence=["totally made up"]), LOG)
    assert out["confidence"] == "low" and any("low" in n for n in notes)


def test_unknown_category_without_evidence_is_left_alone():
    out, _ = ground(d(category="unknown", evidence=[], confidence="low"), LOG)
    assert out["confidence"] == "low"


def test_input_is_not_mutated():
    original = d(evidence=["nope"])
    ground(original, LOG)
    assert original["evidence"] == ["nope"]
