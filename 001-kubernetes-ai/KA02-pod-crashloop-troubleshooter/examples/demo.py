"""Run the diagnosis step against the sample data in this folder —
no live Kubernetes cluster required. Useful for trying the project out
quickly or for testing the LLM call in isolation.

Usage:
    python examples/demo.py

Requires ANTHROPIC_API_KEY set in the environment or a .env file at the
project root.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from src.cli import print_result
from src.troubleshooter import investigate_from_data


def main() -> None:
    load_dotenv()

    here = os.path.dirname(__file__)
    with open(os.path.join(here, "sample_facts.json")) as f:
        facts = json.load(f)
    with open(os.path.join(here, "sample_logs.txt")) as f:
        raw_logs = f.read()

    result = investigate_from_data(facts, raw_logs)
    print_result(result)


if __name__ == "__main__":
    main()
