"""Command-line entrypoint — this is what the GitHub Actions step runs.

In a workflow:
    python -m src.cli build.log

Locally, to see what the bot would say without posting anything:
    python -m src.cli examples/sample_build.log --dry-run

Environment:
    ANTHROPIC_API_KEY   required (set it as a repository secret in Actions)
    GH_TOKEN            needed to post (Actions: ${{ github.token }})
    REPO                owner/name of the repository
    PR_NUMBER           pull request number
    HEAD_SHA            head commit of the pull request
    GITHUB_WORKSPACE    set by Actions; used to shorten absolute paths
"""

import argparse
import os
import re
import sys

from dotenv import load_dotenv

from src.github_client import GitHubError, post_comment
from src.triage import TriageResult, triage_log


def print_result(result: TriageResult) -> None:
    t = result.trace
    print("=" * 60)
    print(f"LOG: {t.total_lines:,} lines | SENT TO THE MODEL: {t.lines_sent} "
          f"(lines {t.start}-{t.end}, {t.fraction:.1%})")
    print("=" * 60)
    if result.locations:
        print("Locations found in the trace (most likely first):")
        for loc in result.locations:
            print(f"  - {loc.path}:{loc.line}")
    else:
        print("No file:line found in the trace.")
    print("\n" + "=" * 60)
    print("COMMENT THAT WOULD BE POSTED")
    print("=" * 60)
    print(result.comment)
    if result.error:
        print(f"[fallback used: {result.error}]")


def _post_settings() -> tuple:
    """Validate the values that end up in an API URL or request body."""
    repo = os.environ.get("REPO", "")
    pr = os.environ.get("PR_NUMBER", "")
    sha = os.environ.get("HEAD_SHA", "")
    if not re.fullmatch(r"[\w.\-]+/[\w.\-]+", repo):
        raise ValueError("REPO must look like owner/name")
    if not pr.isdigit():
        raise ValueError("PR_NUMBER must be a number")
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}", sha):
        raise ValueError("HEAD_SHA must be a commit hash")
    return repo, int(pr), sha


def main(argv=None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="AI triage for a failed CI log")
    parser.add_argument("log_file", help="Path to the saved build log (e.g. build.log)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the comment instead of posting it")
    parser.add_argument("--before", type=int, default=40,
                        help="Log lines to keep before the last error")
    parser.add_argument("--after", type=int, default=15,
                        help="Log lines to keep after the last error")
    parser.add_argument("--model", default=None, help="Override the model name")
    args = parser.parse_args(argv)

    try:
        with open(args.log_file, errors="ignore") as f:
            raw_log = f.read()
    except OSError as e:
        print(f"Cannot read log file: {e}", file=sys.stderr)
        return 2

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # Pull requests from forks never receive repository secrets. That is
        # expected, not an error: say so and leave the build result alone.
        print("ANTHROPIC_API_KEY is not set (is this a fork PR?). Skipping AI triage.")
        return 0

    result = triage_log(
        raw_log,
        before=args.before,
        after=args.after,
        workspace=os.environ.get("GITHUB_WORKSPACE"),
        model=args.model,
    )

    if args.dry_run:
        print_result(result)
        return 0

    try:
        repo, pr, sha = _post_settings()
        outcome = post_comment(repo, pr, sha, result.comment, result.locations)
    except (ValueError, GitHubError) as e:
        print(f"Could not post the comment: {e}", file=sys.stderr)
        return 1

    where = f"inline at {outcome.location.path}:{outcome.location.line}" if outcome.kind == "inline" else "as a PR comment"
    print(f"Posted triage {where}.")
    if outcome.note:
        print(f"Note: {outcome.note}")
    if result.error:
        print(f"Note: AI diagnosis unavailable, posted the raw trace instead ({result.error}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
