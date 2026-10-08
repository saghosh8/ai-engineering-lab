"""
context.py

Turns raw Kubernetes objects (~200 fields on a Pod alone) into a compact,
redacted evidence bundle (~25 fields) suitable for sending to an LLM.

This is the step that determines whether the whole tool works well.
Smaller, cleaner context means lower cost, lower latency, and better
model accuracy — signal isn't diluted by managedFields and defaults.
"""

from __future__ import annotations

from src.redactor import redact

REDACT_KEYWORDS = ("PASSWORD", "SECRET", "TOKEN", "KEY", "CREDENTIAL", "DSN")


def truncate(text: str, head: int = 40, tail: int = 120) -> str:
    """Keep the first `head` and last `tail` lines of a log blob.

    Startup banners live at the top; stack traces and crash output live
    at the bottom. Truncating the middle keeps both ends without paying
    for thousands of repetitive lines in between.
    """
    lines = text.splitlines()
    if len(lines) <= head + tail:
        return text

    omitted = len(lines) - head - tail
    return "\n".join(
        lines[:head]
        + [f"... [{omitted} lines omitted] ..."]
        + lines[-tail:]
    )


def pick_container_status(pod):
    """Choose the container worth investigating.

    Pods with sidecars (service mesh, log shippers) have several
    containers, and the first one is not necessarily the one crashing.
    Preference: containers that have terminated before, then ones that
    are waiting (CrashLoopBackOff, ImagePullBackOff), then most restarts.
    """
    statuses = pod.status.container_statuses or []
    if not statuses:
        return None

    def score(s):
        crashed = bool(s.last_state and s.last_state.terminated)
        waiting = bool(s.state and s.state.waiting)
        return (crashed, waiting, s.restart_count or 0)

    return max(statuses, key=score)


def describe_state(state) -> dict:
    """Collapse a V1ContainerState into {'state': ..., 'reason': ...}
    instead of sending the model a raw Python object repr.
    """
    if state is None:
        return {"state": "unknown", "reason": None}
    if state.waiting:
        return {"state": "waiting", "reason": state.waiting.reason}
    if state.terminated:
        return {"state": "terminated", "reason": state.terminated.reason}
    if state.running:
        return {"state": "running", "reason": None}
    return {"state": "unknown", "reason": None}


def _redact_env_names(env_vars) -> list[str]:
    """Keep env var names for context, but flag anything that looks
    like a secret. We never send env var *values* to the model at all.
    """
    names = []
    for e in env_vars or []:
        if any(keyword in e.name.upper() for keyword in REDACT_KEYWORDS):
            names.append(f"{e.name}=<redacted>")
        else:
            names.append(e.name)
    return names


def _event_time(e) -> str:
    return str(e.last_timestamp or e.event_time or "")


def build_evidence(raw: dict) -> dict:
    """Extract, redact and truncate raw Kubernetes objects into the
    compact evidence bundle that gets sent to the LLM.

    Everything free-text (logs, event messages) is redacted here, before
    it can leave the process.
    """
    pod = raw["pod"]
    events = raw["events"]
    logs = raw["logs"]

    status = pick_container_status(pod)
    container = None
    if status:
        container = next((c for c in pod.spec.containers if c.name == status.name), None)
    container = container or pod.spec.containers[0]

    last_terminated = None
    if status and status.last_state and status.last_state.terminated:
        t = status.last_state.terminated
        last_terminated = {"exit_code": t.exit_code, "reason": t.reason}

    recent_events = sorted(events, key=_event_time)[-15:]

    return {
        "container": container.name,
        "phase": pod.status.phase,
        "restart_count": status.restart_count if status else 0,
        "current_state": describe_state(status.state if status else None),
        "last_terminated": last_terminated,
        "image": container.image,
        "resources": container.resources.to_dict() if container.resources else None,
        "liveness_probe": (
            container.liveness_probe.to_dict() if container.liveness_probe else None
        ),
        "readiness_probe": (
            container.readiness_probe.to_dict() if container.readiness_probe else None
        ),
        "env_names": _redact_env_names(container.env),
        "events": [
            redact(f"{e.type} {e.reason}: {e.message}") for e in recent_events
        ],
        "logs_source": raw.get("logs_source", "unknown"),
        "logs": truncate(redact(logs), head=40, tail=120),
    }
