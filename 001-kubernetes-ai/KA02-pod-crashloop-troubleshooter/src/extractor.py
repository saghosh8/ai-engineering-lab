"""Deterministic extraction of the structured facts that matter for triage.

These fields (exit code, restart count, reason, resource limits, events)
have known, well-defined meanings in Kubernetes. Extracting them is a
parsing problem, not an interpretation problem — so it stays outside the
LLM entirely. Only the free-text log excerpt is handed to the model.
"""

from typing import Any, Dict, List

from src.redactor import redact


def extract_facts(pod, events: List[Any]) -> Dict[str, Any]:
    """Pull restart count, exit code, reason, resource limits, and recent
    events out of the raw Kubernetes API objects.
    """
    container_status = pod.status.container_statuses[0] if pod.status.container_statuses else None
    last_state = container_status.last_state if container_status else None
    terminated = last_state.terminated if last_state else None

    container_spec = pod.spec.containers[0] if pod.spec.containers else None
    resources = container_spec.resources if container_spec else None
    limits = resources.limits if resources and resources.limits else {}

    facts: Dict[str, Any] = {
        "pod_name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "phase": pod.status.phase,
        "restart_count": container_status.restart_count if container_status else None,
        "exit_code": terminated.exit_code if terminated else None,
        "reason": terminated.reason if terminated else None,
        "started_at": str(terminated.started_at) if terminated and terminated.started_at else None,
        "finished_at": str(terminated.finished_at) if terminated and terminated.finished_at else None,
        "resource_limits": dict(limits) if limits else {},
        "recent_events": [
            {
                "reason": e.reason,
                "message": redact(e.message or ""),
                "time": str(e.last_timestamp or e.event_time or ""),
            }
            for e in events
        ],
    }
    return facts
