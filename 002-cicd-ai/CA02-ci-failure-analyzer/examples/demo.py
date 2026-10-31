"""Run the analyzer on every sample log in this folder and print a summary.

Usage:
    python examples/demo.py             # uses the model if ANTHROPIC_API_KEY is set
    python examples/demo.py --no-llm    # rule-based only, no API call

Nothing is sent to GitHub or Jenkins; the logs are local files.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from src.analyzer import analyze
from src.report import render_markdown
from src.signatures import BY_CATEGORY

HERE = Path(__file__).resolve().parent


def main() -> None:
    load_dotenv()
    use_llm = "--no-llm" not in sys.argv
    logs = sorted(HERE.glob("*.log"))
    rows = []
    for path in logs:
        result = analyze(path.read_text(), use_llm=use_llm)
        label = BY_CATEGORY[result.category].label if result.category in BY_CATEGORY else "unknown"
        rows.append((path.name, result.ci, result.step or "-", label, "AI" if result.llm_used else "rules"))

    widths = [max(len(r[i]) for r in rows + [("file", "ci", "step", "likely failure", "by")]) for i in range(5)]
    for row in [("file", "ci", "step", "likely failure", "by")] + rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))

    print("\n--- full report for the first log ---\n")
    print(render_markdown(analyze(logs[0].read_text(), use_llm=use_llm)))


if __name__ == "__main__":
    main()
