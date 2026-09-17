"""
context.py

Turns raw Kubernetes objects (~200 fields on a Pod alone) into a compact,
redacted evidence bundle (~25 fields) suitable for sending to an LLM.

This is the step that determines whether the whole tool works well.
Smaller, cleaner context means lower cost, lower latency, and better
model accuracy — signal isn't diluted by managedFields and defaults.
"""

from __future__ import annotations

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


def _redact_env_names(env_vars) -> list[str]:
    """Keep env var names for context, but redact anything that looks
    like a secret. We never send env var *values* to the model at all.
    """
    names = []
    for e in env_vars or []:
        if any(keyword in e.name.upper() for keyword in REDACT_KEYWORDS):
            names.append(f"{e.name}=<redacted>")
        else:
            names.append(e.name)
    return names


def build_evidence(raw: dict) -> dict:
    """Extract, redact and truncate raw Kubernetes objects into the
    compact evidence bundle that gets sent to the LLM.
    """
    pod = raw["pod"]
    events = raw["events"]
    logs = raw["logs"]

    if not pod.status.container_statuses:
        status = None
    else:
        status = pod.status.container_statuses[0]

    container = pod.spec.containers[0]

    last_terminated = None
    if status and status.last_state and status.last_state.terminated:
        t = status.last_state.terminated
        last_terminated = {"exit_code": t.exit_code, "reason": t.reason}

    return {
        "phase": pod.status.phase,
        "restart_count": status.restart_count if status else 0,
        "current_state": str(status.state) if status else "unknown",
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
            f"{e.type} {e.reason}: {e.message}" for e in events[-15:]
        ],
        "logs": truncate(logs, head=40, tail=120),
    }
