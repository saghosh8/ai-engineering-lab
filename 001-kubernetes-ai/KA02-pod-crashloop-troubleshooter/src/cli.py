"""Command-line entrypoint.

Usage:
    python -m src.cli --namespace payments --pod payment-worker-7d9f8c-xk2p1

Requires a working kubeconfig (or in-cluster credentials) and
ANTHROPIC_API_KEY set in the environment or a .env file.
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from src.troubleshooter import TroubleshootResult, investigate_pod


def print_result(result: TroubleshootResult) -> None:
    print("\n" + "=" * 60)
    print("EVIDENCE (deterministic)")
    print("=" * 60)
    print(json.dumps(result.facts, indent=2))
    print("\nLog excerpt (redacted, tail):")
    print(result.log_excerpt[-1000:])  # keep terminal output sane

    print("\n" + "=" * 60)
    print("AI DIAGNOSIS (hypothesis — verify before acting)")
    print("=" * 60)

    if not result.succeeded:
        print(f"No AI diagnosis available: {result.error}")
        print("Falling back to the raw evidence above. Investigate manually.")
        return

    d = result.diagnosis
    print(f"Likely cause     : {d.likely_cause}")
    print(f"Confidence       : {d.confidence.upper()}")
    print("Evidence:")
    for item in d.evidence:
        print(f"  - {item}")
    print(f"Next step        : {d.recommended_next_step}")
    print()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="AI-assisted CrashLoopBackOff investigator"
    )
    parser.add_argument("--namespace", required=True, help="Kubernetes namespace")
    parser.add_argument("--pod", required=True, help="Pod name")
    parser.add_argument("--tail-lines", type=int, default=100, help="Log lines to fetch")
    parser.add_argument("--kubeconfig", default=None, help="Path to kubeconfig (optional)")

    args = parser.parse_args()

    try:
        result = investigate_pod(
            namespace=args.namespace,
            pod_name=args.pod,
            tail_lines=args.tail_lines,
            kubeconfig=args.kubeconfig,
        )
    except Exception as e:
        print(f"Failed to investigate pod: {e}", file=sys.stderr)
        sys.exit(1)

    print_result(result)


if __name__ == "__main__":
    main()
