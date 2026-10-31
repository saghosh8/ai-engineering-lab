"""The README promises a result for each sample log. Keep that promise true."""

import pytest

from src.analyzer import analyze
from src.signatures import BY_CATEGORY
from tests.conftest import EXAMPLES, sample

# Same rows as the table in README-CA02.md ("Try it locally").
EXPECTED = [
    ("gha_dependency_404.log", "github-actions", "Dependency could not be installed", "Run npm ci"),
    ("gha_test_failure.log", "github-actions", "Test failure", "Run pytest -q"),
    ("gha_network_flake.log", "github-actions", "Network or registry problem", "Run npm ci"),
    ("jenkins_out_of_memory.log", "jenkins", "Out of memory", "Build"),
    ("jenkins_docker_auth.log", "jenkins", "Authentication or permission error", "Push image"),
]


@pytest.mark.parametrize("name,ci,label,step", EXPECTED)
def test_sample_matches_the_readme_table(name, ci, label, step):
    r = analyze(sample(name), use_llm=False)
    assert (r.ci, BY_CATEGORY[r.category].label, r.step) == (ci, label, step)


def test_every_sample_log_is_in_the_table():
    assert sorted(p.name for p in EXAMPLES.glob("*.log")) == sorted(e[0] for e in EXPECTED)


def test_readme_table_rows_exist_in_the_readme():
    readme = (EXAMPLES.parent / "README-CA02.md").read_text()
    for name, _, label, step in EXPECTED:
        row = next(line for line in readme.splitlines() if f"`{name}`" in line)
        assert label in row and step in row
