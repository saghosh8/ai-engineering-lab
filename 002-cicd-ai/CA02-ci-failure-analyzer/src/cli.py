"""Command-line entry point.

    python -m src.cli build.log                      # a saved log (or - for stdin)
    python -m src.cli --gh-run 123456 --repo me/app  # a GitHub Actions run
    python -m src.cli --jenkins-url https://ci.example.com/job/app/42/

Add --format json for scripts, --no-llm to skip the model entirely.
"""

import argparse
import os
import sys
from typing import List, Optional

from dotenv import load_dotenv

from src.analyzer import analyze
from src.report import render_json, render_markdown
from src.sources import SourceError, fetch_github_run, fetch_jenkins, read_file


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ci-analyzer", description="Find the likely cause of a failed CI/CD run.")
    p.add_argument("logfile", nargs="?", help="path to a saved log, or - for stdin")
    p.add_argument("--gh-run", metavar="RUN_ID", help="fetch failed-step logs of a GitHub Actions run (needs --repo and gh)")
    p.add_argument("--repo", metavar="OWNER/NAME", help="repository for --gh-run")
    p.add_argument("--jenkins-url", metavar="URL", help="build URL of a Jenkins job; its console text is fetched")
    p.add_argument("--ci", choices=["auto", "github-actions", "jenkins"], default="auto")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--no-llm", action="store_true", help="rule-based result only; no API call")
    p.add_argument("--model", help="override the model (default: ANALYZER_MODEL or claude-sonnet-5-5)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    sources = [bool(args.logfile), bool(args.gh_run), bool(args.jenkins_url)]
    if sum(sources) != 1:
        parser.error("give exactly one of: a log file, --gh-run, --jenkins-url")
    if args.gh_run and not args.repo:
        parser.error("--gh-run needs --repo")

    try:
        if args.logfile:
            raw = read_file(args.logfile)
        elif args.gh_run:
            raw = fetch_github_run(args.gh_run, args.repo)
        else:
            raw = fetch_jenkins(args.jenkins_url, os.environ.get("JENKINS_USER"), os.environ.get("JENKINS_TOKEN"))
    except SourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = analyze(raw, ci=args.ci, use_llm=not args.no_llm, model=args.model)
    sys.stdout.write(render_json(result) if args.format == "json" else render_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
