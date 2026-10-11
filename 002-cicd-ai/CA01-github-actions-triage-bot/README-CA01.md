# CA01 — GitHub Actions AI Triage Bot

When a CI step fails, a small bot reads the log for you, finds the real
error, and posts a plain-language diagnosis on the pull request — so
nobody has to scroll through 4,000 lines to find one exit code.

[![Substack](https://img.shields.io/badge/%F0%9F%93%96%20READ%20THE%20ARTICLE-CA01-F5EEDC?style=for-the-badge&labelColor=1237A)](https://techworldwithsahana.substack.com/p/circuit-breaker-pattern-vs-rate-limiter)

Understand the concepts behind this build: *Build an AI-Powered GitHub Actions Triage Bot: From Raw Logs to Root Cause.*

<!-- TODO: add the architecture image, then uncomment:
[![CA01 architecture](https://github.com/saghosh8/ai-engineering-lab/raw/main/002-cicd-ai/images/CA01.jpg)](/saghosh8/ai-engineering-lab/blob/main/002-cicd-ai/images/CA01.jpg)
-->

## What this is

A GitHub Actions step plus a small Python CLI. When the test step fails,
the workflow hands the saved log to the CLI and a diagnosis appears on
the pull request.

```
$ python -m src.cli build.log
Posted triage inline at app/src/cart.js:42.
```

- **Input:** the saved log of the failed step (`build.log`), plus the PR
  number, repo and head commit from the workflow environment
- **Processing (deterministic):** strip ANSI colors and progress-bar
  rewrites, redact secrets, find the last stack trace and keep a 55-line
  window around it, pull out `file:line` references, check which of them
  are part of the PR diff
- **AI (one call):** a short Markdown diagnosis — **Root cause**,
  **Where**, **Suggested fix**
- **Output:** an inline review comment on the broken line when possible,
  a normal PR comment otherwise

No agent. No tool calling. No RAG. The model never touches your
repository or the GitHub API — our code does all of that.

## How a failed build flows

```
failed step ─▶ log file ─▶ clean ─▶ extract trace ─▶ LLM ─▶ PR comment
 (workflow)    (tee)      cleaner     extractor     llm_client  github_client
 └────────────── our code ────────────────────────┘ └─ external API ─┘
```

| Step | What happens | Where |
| ---- | ------------ | ----- |
| 1. Catch the failure | `continue-on-error` + `steps.tests.outcome == 'failure'`; `tee` saves the log | `workflow/ca01-triage-demo.yml` |
| 2. Clean the log | ANSI codes, carriage returns, secrets | `src/cleaner.py`, `src/redactor.py` |
| 3. Find the real error | last error line + 40 lines before, 15 after | `src/extractor.py` |
| 4. Ask the LLM | one call, ≤ 500 output tokens | `src/llm_client.py` |
| 5. Post it | inline if the line is in the diff, else a PR comment | `src/github_client.py` |

## Project layout

```
CA01-github-actions-triage-bot/
├── src/
│   ├── cleaner.py        # ANSI + carriage-return cleanup, then redaction
│   ├── redactor.py       # secret/PII redaction
│   ├── extractor.py      # last stack trace window + file:line references
│   ├── llm_client.py     # the single LLM call, prompt, reply validation
│   ├── formatter.py      # PR comment text (diagnosis or raw-trace fallback)
│   ├── github_client.py  # PR diff lookup, inline/PR comments via `gh`
│   ├── triage.py         # pipeline orchestration
│   └── cli.py            # entry point the workflow runs
├── workflow/
│   └── ca01-triage-demo.yml   # copy to .github/workflows/
├── demo-app/              # tiny Node project with one intentional bug
├── tests/                 # pytest, no GitHub or API key needed
├── examples/              # a real captured failing log + demo script
│   ├── sample_build.log
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

## Try it locally (no GitHub needed)

`examples/sample_build.log` is a real capture of the demo app failing
under `FORCE_COLOR=1`, so it contains the same color codes you see in the
Actions UI.

```
python examples/demo.py

# or, with the CLI
python -m src.cli examples/sample_build.log --dry-run
```

`--dry-run` prints the comment instead of posting it. This still makes a
real call to the Anthropic API — it skips GitHub, not the LLM.
`ANTHROPIC_API_KEY` must be set; without it the demo shows the fallback
comment (the extracted trace) instead of a diagnosis.

## Use it in GitHub Actions

1. Copy `workflow/ca01-triage-demo.yml` to `.github/workflows/` in your
   repository (GitHub only runs workflows from there) and set `BOT_DIR`
   and `APP_DIR` at the top of the file.
2. Add a repository secret named `ANTHROPIC_API_KEY`
   (Settings → Secrets and variables → Actions).
3. Open a pull request. When the test step fails, the bot comments.

To see it work end to end, open a PR that **adds `demo-app/`**. Its test
`applies discount to empty cart` fails because `applyDiscount` calls
`reduce` on an empty array (`demo-app/src/cart.js`, line 42). The whole
file is part of the diff, so the comment lands inline on that line.

Why the workflow looks the way it does:

| Piece | Reason |
| ----- | ------ |
| `continue-on-error: true` on the test step | lets the next steps run even though tests failed |
| `npm test 2>&1 \| tee build.log` + `exit ${PIPESTATUS[0]}` | saves the log *and* keeps the test command's real exit code (`tee` alone would report success) |
| `FORCE_COLOR: "1"` | same colored output as the Actions UI, so the cleaner is exercised |
| `if: steps.tests.outcome == 'failure'` | the bot only runs when there is something to diagnose |
| `head.repo.full_name == github.repository` | pull requests from forks get no secrets, so the bot skips them |
| `continue-on-error: true` on the triage step | a broken bot must never hide the real failure |
| final `exit 1` step | the PR still shows a red cross |

To use the bot in another repository, copy `src/` and `requirements.txt`
into a folder there (for example `tools/triage-bot/`) and point `BOT_DIR`
at it.

## Configuration

| Variable | Used for |
| -------- | -------- |
| `ANTHROPIC_API_KEY` | the LLM call (required) |
| `GH_TOKEN` | posting the comment (Actions: `${{ github.token }}`) |
| `REPO`, `PR_NUMBER`, `HEAD_SHA` | where to post (set by the workflow) |
| `GITHUB_WORKSPACE` | set by Actions; turns absolute paths into repo-relative ones |
| `TRIAGE_MODEL` / `ANTHROPIC_MODEL` | override the model (default `claude-sonnet-5-5`) |

CLI flags: `--dry-run`, `--before 40`, `--after 15`, `--model <name>`.

## Running the tests

```
pip install -r requirements-dev.txt
pytest
```

The tests fake the model and the `gh` CLI and run against a real captured
log, so they need neither GitHub nor an API key. They also check the
workflow file itself (trigger, permissions, step order, fork guard) and
that the demo app's bug still sits on the line the README names.

## Security notes

- **Least privilege.** The workflow asks for `contents: read` and
  `pull-requests: write`, nothing else.
- **No `pull_request_target`.** Code from a PR is never run with the
  repository's secrets. Fork PRs are skipped.
- **The log is untrusted input.** It is wrapped in `<log>` tags, the
  prompt tells the model never to follow instructions found inside it,
  and the model has no tools. The worst a hostile log can do is produce a
  misleading comment, which is why every comment is labelled AI-generated.
- **Redaction before anything leaves the runner** (`redactor.py`), also
  applied to the fallback comment.
- **No shell injection.** `gh` is always called with an argument list, and
  `REPO`, `PR_NUMBER` and `HEAD_SHA` are validated before use.
- **Errors stay private.** The PR comment gets a short generic reason;
  full error details go only to the step log.

## Known limitations

- The model sees about 55 log lines, not your code. Treat the diagnosis
  as a hint; it can be wrong.
- An inline comment needs a `file:line` from the trace that is part of
  the PR diff. Assertion failures usually point at the test file, so those
  end up as a normal PR comment.
- Error detection is keyword-based (`Error:`, `FAIL`, `Traceback`,
  `panic:`, …). If nothing matches, the tail of the log is used. Footer
  lines such as `npm ERR!` are skipped as the anchor.
- One comment per failed run: a re-run posts another one. Updating the
  existing comment in place is a natural next step.
- No flaky-test detection and no commit history in the prompt.
- Redaction is regex-based: it is a safety net, not a guarantee. Add your
  own token formats and internal hostnames before using this on a private
  repository.
- Cost is bounded by design: it only runs on failures, sends ~55 lines,
  and caps the answer at 500 tokens.
- Verified end to end on Node (Jest). The unit tests also cover Python,
  Java and compiler-style (`file:line:col`) traces; other tools work if
  they print `file:line`.

---

## ⭐ Support

If you found this repository useful:

[![Stars](https://img.shields.io/github/stars/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&label=STAR%20THIS%20REPO)](https://github.com/saghosh8/ai-engineering-lab)
[![Forks](https://img.shields.io/github/forks/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&label=FORK)](https://github.com/saghosh8/ai-engineering-lab/fork)
