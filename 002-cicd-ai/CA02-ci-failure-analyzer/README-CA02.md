# CA02 — AI CI/CD Failure Analyzer

Point it at a failed GitHub Actions or Jenkins log. It tells you which
kind of failure it was, shows the log lines that prove it, and explains
the likely cause in plain language — without sending the whole log to a
model.

<!-- TODO: add the article link and architecture image when published -->

## What this is

A small Python CLI. It reads a log from a file, a GitHub Actions run or a
Jenkins build, and prints a report.

```
$ python -m src.cli examples/jenkins_docker_auth.log

## CI failure analysis

**Likely failure:** Authentication or permission error, confidence **high**
**CI:** Jenkins · **Failed step:** Push image
...
```

- **Input:** a saved log (or `-` for stdin), a GitHub Actions run id, or a Jenkins build URL
- **Processing (deterministic):** strip colors, timestamps and progress bars,
  redact secrets, detect the CI system and the failed step, rank likely
  failure categories from a catalog of known error patterns
- **AI (one call):** a small JSON answer: category, likely cause, quoted
  evidence, confidence, flaky or not, next steps
- **Verification (deterministic):** every line the model quotes must exist
  in the log, or it is removed
- **Output:** a Markdown report (or JSON) that keeps what the log *shows*
  separate from what the model *thinks*

No agent. No tool calling. No RAG. The model never touches your CI
server, your repository or the network.

## How CA02 differs from CA01

| | CA01 | CA02 |
| - | ---- | ---- |
| Question | "Why did this PR's test fail?" | "What *kind* of failure is this?" |
| CI systems | GitHub Actions | GitHub Actions and Jenkins |
| Detection | last stack trace | ranked catalog of 12 failure categories |
| Model output | Markdown comment | validated JSON with confidence |
| Fact-check | none | quoted evidence must appear in the log |
| Without a model | raw trace | full rule-based report |
| Output goes to | an inline PR comment | stdout, JSON or the job summary |

## How a failed run flows

```
log ─▶ normalize ─▶ detect ─▶ classify ─▶ LLM ─▶ ground ─▶ report
      normalizer   detector  classifier  llm_client grounding report
      └──────────── our code ───────────┘ └ API ┘ └─ our code ─┘
```

| Step | What happens | Where |
| ---- | ------------ | ----- |
| 1. Normalize | colors, `\r`, timestamps, job prefixes removed; secrets redacted | `src/normalizer.py`, `src/redactor.py` |
| 2. Detect | GitHub Actions or Jenkins; which step or stage failed | `src/detector.py` |
| 3. Classify | match the failure catalog, score and rank, keep evidence lines | `src/signatures.py`, `src/classifier.py` |
| 4. Pick context | top hints, ~55 numbered lines around the evidence, last lines | `src/context.py` |
| 5. Ask the LLM | one call, ≤ 600 output tokens, JSON only | `src/llm_client.py` |
| 6. Ground | drop quotes that are not in the log; cap confidence | `src/grounding.py` |
| 7. Report | Markdown or JSON | `src/report.py` |

### The failure catalog

`disk_space`, `out_of_memory`, `infrastructure` (runner or agent lost),
`auth_permission`, `missing_config`, `dependency_install`,
`container_build`, `timeout`, `network`, `compile_error`, `lint_format`
and `test_failure`. Each is a handful of regular expressions in
`src/signatures.py`. Add your own tools' error messages there.

A category's score is `weight + 0.4 × matching lines (max 5) + 2 × position
in the log`. Specific causes weigh more than generic ones, so a log with an
out-of-memory kill *and* a failed test ranks out-of-memory first: the
memory problem is what broke the test. The position bonus reflects that
the real cause is usually near the end of a log.

## Project layout

```
CA02-ci-failure-analyzer/
├── src/
│   ├── normalizer.py   # ANSI, \r, timestamps, prefixes, then redaction
│   ├── redactor.py     # secret/PII redaction
│   ├── detector.py     # GitHub Actions vs Jenkins, failed step or stage
│   ├── signatures.py   # the failure catalog (edit this)
│   ├── classifier.py   # scoring and evidence
│   ├── context.py      # what the model gets to see
│   ├── llm_client.py   # the single LLM call, prompt, JSON validation
│   ├── grounding.py    # evidence-in-log check
│   ├── analyzer.py     # pipeline orchestration, offline fallback
│   ├── report.py       # Markdown and JSON output
│   ├── sources.py      # file, stdin, `gh run view`, Jenkins consoleText
│   └── cli.py          # entry point
├── workflow/
│   └── ca02-analyze-failed-run.yml   # copy to .github/workflows/
├── tests/              # pytest, no network, CI server or API key needed
├── examples/           # five sample logs + demo script
│   ├── gha_dependency_404.log
│   ├── gha_test_failure.log
│   ├── gha_network_flake.log
│   ├── jenkins_out_of_memory.log
│   ├── jenkins_docker_auth.log
│   └── demo.py
├── requirements.txt
└── .env.example
```

## Setup

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # add -r requirements-dev.txt to run tests
cp .env.example .env              # fill in ANTHROPIC_API_KEY
```

## Try it locally

The sample logs are synthetic: realistic in shape, with made-up names.

```
python examples/demo.py --no-llm     # rule-based only, no API key needed
python examples/demo.py              # adds the AI step if ANTHROPIC_API_KEY is set

python -m src.cli examples/gha_network_flake.log
python -m src.cli examples/gha_network_flake.log --format json
python -m src.cli --no-llm examples/jenkins_out_of_memory.log
```

Without an API key (or if the model call fails) the report still appears,
marked *rule-based only*.

## Use it on a real run

**A saved log**

```
python -m src.cli build.log
cat build.log | python -m src.cli -
```

**A GitHub Actions run** (needs the `gh` CLI, logged in)

```
python -m src.cli --gh-run 123456789 --repo owner/name
```

This reads the logs of the failed steps only (`gh run view --log-failed`).
GitHub makes logs available once a run has finished.

**A Jenkins build**

```
python -m src.cli --jenkins-url https://ci.example.com/job/app/42/
```

It fetches `<url>/consoleText`. For a private Jenkins set `JENKINS_USER`
and `JENKINS_TOKEN` (a user API token) in `.env`.

**Automatically, after a GitHub Actions failure**

Copy `workflow/ca02-analyze-failed-run.yml` to `.github/workflows/`, set
the name of the workflow to watch, and add the `ANTHROPIC_API_KEY`
repository secret. When that workflow fails, the report appears in the
analysis job's summary. The analyzer must live in your repository (copy
`src/` and `requirements.txt`).

## Configuration

| Variable | Used for |
| -------- | -------- |
| `ANTHROPIC_API_KEY` | the LLM call (optional; without it you get the rule-based report) |
| `ANALYZER_MODEL` / `ANTHROPIC_MODEL` | override the model (default `claude-sonnet-5-5`) |
| `JENKINS_USER`, `JENKINS_TOKEN` | only for `--jenkins-url` on a private Jenkins |
| `GH_TOKEN` | only for `--gh-run` outside your own `gh login` (Actions: `${{ github.token }}`) |

CLI flags: `--ci auto|github-actions|jenkins`, `--format md|json`,
`--no-llm`, `--model <name>`.

## Running the tests

```
pip install -r requirements-dev.txt
pytest
```

The tests fake the model, `gh` and the HTTP call, so they need no network
and no API key. They check each stage on the sample logs, the fallbacks
(no key, API error, garbage output), the fact-check, that passing logs are
never reported as failures, that secrets never reach the model, and the
workflow file's trigger, permissions and shell safety.

## Security notes

- **The log is untrusted input.** It is wrapped in `<log>` tags, the
  prompt says never to follow instructions inside it, and the model has no
  tools. The worst a hostile log can do is produce a misleading report.
- **The model is fact-checked.** Quoted evidence that is not in the log is
  removed; with no verified evidence, confidence is forced to *low*. When
  the model and the rules disagree, the report says so and caps confidence.
- **Redaction before anything leaves your machine** (`redactor.py`), on
  every path including the rule-based report.
- **Least privilege in Actions.** The workflow asks for `actions: read` and
  `contents: read`, checks out no pull request code, and passes values to
  the shell through `env`, never by interpolating `${{ }}` into a script.
- **No shell injection.** `gh` is called with an argument list; the run id
  must be numeric and `--repo` must look like `owner/name`. Jenkins URLs
  must be `http(s)`. Error messages never echo response bodies.
- **Bounded input.** Only the last 5 MB of a log is read, and the model
  sees about 55 lines plus the tail.

## Known limitations

- The model sees a small window of the log, not your code. The report is a
  hint to check, not a verdict.
- The catalog is pattern-based. A failure that matches no pattern is still
  sent to the model with no hints, but expect `unknown` more often. Extend
  `src/signatures.py` for your own tools.
- The category ranking is a heuristic. Two real causes in one log (for
  example, a network error and then a timeout) can rank in the wrong
  order; the report lists the top three so you can see both.
- Flaky detection is the model's judgement from one log. There is no
  history of past runs.
- The model call is covered by tests with a fake client. Run
  `examples/demo.py` with your key to see it live; the workflow file has
  not been run on GitHub.
- Running the analyzer from inside a Jenkins `post { failure { ... } }`
  block reads a log that is still being written, so the last lines can be
  missing. A downstream job that runs after the build avoids this.
- Redaction is regex-based: a safety net, not a guarantee. Add your own
  token formats and internal hostnames before using it on private logs.
- Cost is bounded: one call per failed run, about 55 lines in, 600 tokens
  out, and no call at all for logs that show no failure.

---

## ⭐ Support

If you found this repository useful:

[![Stars](https://img.shields.io/github/stars/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&label=STAR%20THIS%20REPO)](https://github.com/saghosh8/ai-engineering-lab)
[![Forks](https://img.shields.io/github/forks/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&label=FORK)](https://github.com/saghosh8/ai-engineering-lab/fork)
