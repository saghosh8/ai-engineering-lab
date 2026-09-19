"""Orchestrates the full pipeline: collect -> extract -> redact -> diagnose.

This is the module both the CLI (src/cli.py) and the demo script
(examples/demo.py) call into.
"""

from typing import Any, Dict, Optional

from pydantic import ValidationError

from src import k8s_client
from src.extractor import extract_facts
from src.llm_client import diagnose
from src.models import Diagnosis
from src.redactor import redact


class TroubleshootResult:
    """Wraps either a validated Diagnosis or a fallback with an error and
    the raw evidence, so the caller always has something useful to show.
    """

    def __init__(self, facts: Dict[str, Any], log_excerpt: str,
                 diagnosis: Optional[Diagnosis] = None, error: Optional[str] = None):
        self.facts = facts
        self.log_excerpt = log_excerpt
        self.diagnosis = diagnosis
        self.error = error

    @property
    def succeeded(self) -> bool:
        return self.diagnosis is not None


def investigate_pod(namespace: str, pod_name: str, tail_lines: int = 100,
                     kubeconfig: Optional[str] = None) -> TroubleshootResult:
    """Full pipeline against a real cluster."""
    k8s_client.load_config(kubeconfig=kubeconfig)

    pod = k8s_client.get_pod(namespace, pod_name)
    events = k8s_client.get_events(namespace, pod_name)
    raw_logs = k8s_client.get_logs(namespace, pod_name, tail_lines=tail_lines)

    facts = extract_facts(pod, events)
    log_excerpt = redact(raw_logs)

    return _run_diagnosis(facts, log_excerpt)


def investigate_from_data(facts: Dict[str, Any], raw_logs: str) -> TroubleshootResult:
    """Pipeline entrypoint for pre-collected data. Used by examples/demo.py
    so the diagnosis step can be exercised without a live cluster.
    """
    log_excerpt = redact(raw_logs)
    return _run_diagnosis(facts, log_excerpt)


def _run_diagnosis(facts: Dict[str, Any], log_excerpt: str) -> TroubleshootResult:
    try:
        result = diagnose(facts, log_excerpt)
        return TroubleshootResult(facts, log_excerpt, diagnosis=result)
    except ValidationError as e:
        return TroubleshootResult(facts, log_excerpt, error=f"Model response failed validation: {e}")
    except Exception as e:
        return TroubleshootResult(facts, log_excerpt, error=f"LLM call failed: {e}")
