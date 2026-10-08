"""
cli.py

Entry point.

    python -m src.cli investigate <pod-name> -n <namespace>

Wires together:
  collector.py  -> raw Kubernetes objects (read-only)
  context.py    -> compact, redacted evidence bundle
  analyzer.py   -> LLM call + schema validation + evidence check

Keeps evidence (facts) and interpretation (model output) visually
separate in the printed report, so nobody mistakes a hypothesis for
a confirmed root cause.
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv
from kubernetes.client.exceptions import ApiException

from src import collector, context
from src.analyzer import AnalysisError, call_llm, verify_evidence_grounding


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="k8s-assist",
        description="Investigate a Kubernetes pod with AI-assisted analysis.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    investigate = sub.add_parser("investigate", help="Investigate a single pod")
    investigate.add_argument("pod", help="Pod name")
    investigate.add_argument("-n", "--namespace", required=True, help="Namespace")
    investigate.add_argument(
        "--in-cluster",
        action="store_true",
        help="Use in-cluster ServiceAccount instead of local kubeconfig",
    )
    investigate.add_argument(
        "--save-evidence",
        metavar="PATH",
        help="Also write the raw evidence bundle to this file",
    )

    return parser


def print_report(evidence: dict, analysis) -> None:
    print("\n" + "=" * 70)
    print("EVIDENCE (observed facts)")
    print("=" * 70)
    print(f"container:      {evidence['container']}")
    print(f"phase:          {evidence['phase']}")
    print(f"restart_count:  {evidence['restart_count']}")
    print(f"last_terminated: {evidence['last_terminated']}")
    print(f"current_state:  {evidence['current_state']}")
    print(f"logs_source:    {evidence['logs_source']}")
    print(f"image:          {evidence['image']}")
    print(f"resources:      {evidence['resources']}")

    print("\n" + "=" * 70)
    print("AI INTERPRETATION (not a confirmed root cause)")
    print("=" * 70)
    print(f"\n{analysis.summary}\n")

    for i, hyp in enumerate(analysis.hypotheses, 1):
        print(f"Hypothesis {i} — {hyp.cause} — confidence: {hyp.confidence}")
        for ev in hyp.evidence:
            flag = "  (UNVERIFIED)" if ev in hyp.unverified_evidence else ""
            print(f"  evidence: {ev}{flag}")
        for step in hyp.next_steps:
            print(f"  next step: {step}")
        print()

    if analysis.missing_information:
        print("Missing information:")
        for item in analysis.missing_information:
            print(f"  - {item}")
    print()


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "investigate":
        load_dotenv()

        try:
            v1 = collector.load_client(in_cluster=args.in_cluster)
            raw = collector.collect(v1, name=args.pod, namespace=args.namespace)
        except ApiException as e:
            print(
                f"Kubernetes API error ({e.status} {e.reason}) for pod "
                f"{args.namespace}/{args.pod}. Check the name, namespace and RBAC.",
                file=sys.stderr,
            )
            return 1
        evidence = context.build_evidence(raw)

        if args.save_evidence:
            with open(args.save_evidence, "w") as f:
                json.dump(evidence, f, indent=2)

        try:
            analysis = call_llm(evidence)
        except AnalysisError as e:
            path = args.save_evidence or "./evidence.json"
            with open(path, "w") as f:
                json.dump(evidence, f, indent=2)
            print(f"AI analysis failed: {e}\nEvidence saved to {path}", file=sys.stderr)
            return 1
        analysis = verify_evidence_grounding(analysis, evidence)

        print_report(evidence, analysis)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
