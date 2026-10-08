"""Deterministic extraction of the structured facts that matter for triage.

These fields (exit code, restart count, reason, resource limits, events)
have known, well-defined meanings in Kubernetes. Extracting them is a
parsing problem, not an interpretation problem — so it stays outside the
LLM entirely. Only the free-text log excerpt is handed to the model.
"""

from typing import Any, Dict, List, Optional

from src.redactor import redact


def pick_container_status(pod) -> Optional[Any]:
    """Choose the container worth investigating.

    Pods with sidecars (service mesh, log shippers) have several
    containers, and the first one is not necessarily the one crashing.
    Preference: containers that have terminated before, then the most
    restarts, then simply the first one.
    """
    statuses = pod.status.container_statuses or []
    if not statuses:
        return None

    def score(s):
        crashed = bool(s.last_state and s.last_state.terminated)
        waiting = bool(s.state and s.state.waiting)
        return (crashed, waiting, s.restart_count or 0)

    return max(statuses, key=score)


def describe_state(state) -> Dict[str, Any]:
    """Collapse a V1ContainerState into {'state': ..., 'reason': ...}."""
    if state is None:
        return {"state": "unknown", "reason": None}
    if state.waiting:
        return {"state": "waiting", "reason": state.waiting.reason}
    if state.terminated:
        return {"state": "terminated", "reason": state.terminated.reason}
    if state.running:
        return {"state": "running", "reason": None}
    return {"state": "unknown", "reason": None}


def extract_facts(pod, events: List[Any]) -> Dict[str, Any]:
    """Pull restart count, exit code, reason, resource limits, and recent
    events out of the raw Kubernetes API objects.
    """
    container_status = pick_container_status(pod)
    last_state = container_status.last_state if container_status else None
    terminated = last_state.terminated if last_state else None

    container_spec = None
    if container_status:
        container_spec = next(
            (c for c in pod.spec.containers if c.name == container_status.name), None
        )
    if container_spec is None and pod.spec.containers:
        container_spec = pod.spec.containers[0]
    resources = container_spec.resources if container_spec else None
    limits = resources.limits if resources and resources.limits else {}

    facts: Dict[str, Any] = {
        "pod_name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "container": container_status.name if container_status else None,
        "phase": pod.status.phase,
        "current_state": describe_state(container_status.state if container_status else None),
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
