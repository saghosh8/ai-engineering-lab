import json

from src.analyzer import analyze
from src.report import render_json, render_markdown
from tests.conftest import FakeClient, sample

DEP = sample("gha_dependency_404.log")


def test_markdown_separates_facts_from_interpretation():
    md = render_markdown(analyze(DEP, client=FakeClient()))
    assert "**Likely failure:** Dependency could not be installed, confidence **high**" in md
    assert md.index("What the log shows") < md.index("Interpretation (AI)")
    assert "**Next steps:**" in md and "Verify against the full log" in md


def test_markdown_without_a_model_says_so():
    md = render_markdown(analyze(DEP, use_llm=False))
    assert "Not available: AI step turned off" in md and "rule-based only" in md


def test_markdown_for_a_clean_log():
    md = render_markdown(analyze("Finished: SUCCESS\n", use_llm=False))
    assert "No failure" in md and "Interpretation" not in md


def test_flaky_flag_is_shown():
    from tests.conftest import diagnosis_json
    r = analyze(sample("gha_network_flake.log"), client=FakeClient(text=diagnosis_json(
        category="network", flaky_suspected=True, evidence=["npm error code ETIMEDOUT"])))
    assert "Possibly flaky" in render_markdown(r)


def test_json_is_valid_and_complete():
    data = json.loads(render_json(analyze(DEP, client=FakeClient())))
    assert data["category"] == "dependency_install" and data["ci"] == "github-actions"
    assert data["llm_used"] is True and data["candidates"][0]["evidence"][0]["line_no"] > 0


def test_json_for_a_clean_log_has_no_category():
    assert json.loads(render_json(analyze("Finished: SUCCESS\n", use_llm=False)))["category"] is None
