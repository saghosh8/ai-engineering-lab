"""Run the whole pipeline against the sample log in this folder — no
GitHub and no real CI run required. It prints the comment the bot would
post instead of posting it.

Usage:
    python examples/demo.py

Requires ANTHROPIC_API_KEY set in the environment or a .env file at the
project root. Without it the demo still runs, but shows the fallback
comment (the extracted trace) instead of an AI diagnosis.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from src.cli import print_result
from src.triage import triage_log


def main() -> None:
    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Note: ANTHROPIC_API_KEY is not set, so the model call will fail and "
              "the fallback comment (the extracted trace) is shown instead.\n")

    here = os.path.dirname(__file__)
    with open(os.path.join(here, "sample_build.log"), errors="ignore") as f:
        raw_log = f.read()

    print_result(triage_log(raw_log))


if __name__ == "__main__":
    main()
