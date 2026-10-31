from src.classifier import classify
from src.context import MAX_EXCERPT_CHARS, build_context, build_excerpt, build_hints
from src.normalizer import normalize
from tests.conftest import sample


def test_excerpt_lines_are_numbered_and_include_the_error():
    lines = normalize(sample("gha_dependency_404.log"))[1]
    excerpt = build_excerpt(lines, classify(lines))
    assert "L" in excerpt and "npm error code E404" in excerpt
    assert any(line.startswith("L") and ": " in line for line in excerpt.splitlines())


def test_excerpt_window_is_bounded_and_keeps_the_tail():
    lines = [f"noise {i}" for i in range(500)] + ["ETIMEDOUT", "tail line"]
    excerpt = build_excerpt(lines, classify(lines))
    assert "noise 0" not in excerpt and "tail line" in excerpt


def test_no_candidates_falls_back_to_the_last_lines():
    lines = [f"line {i}" for i in range(200)]
    excerpt = build_excerpt(lines, [])
    assert "line 199" in excerpt and "line 100" not in excerpt


def test_excerpt_is_capped_in_size_and_keeps_the_end():
    lines = ["x" * 400 for _ in range(100)] + ["ETIMEDOUT", "THE END"]
    excerpt = build_excerpt(lines, classify(lines))
    assert len(excerpt) <= MAX_EXCERPT_CHARS + 10 and excerpt.endswith("THE END")


def test_hints_list_candidates_with_evidence():
    lines = normalize(sample("jenkins_out_of_memory.log"))[1]
    hints = build_hints(classify(lines))
    assert "out_of_memory" in hints and "OutOfMemoryError" in hints
    assert build_hints([]) == "(no known failure pattern matched)"


def test_context_names_ci_and_step():
    lines = normalize(sample("jenkins_docker_auth.log"))[1]
    ctx = build_context("jenkins", "Push image", lines, classify(lines))
    assert "CI system: jenkins" in ctx and "Push image" in ctx
