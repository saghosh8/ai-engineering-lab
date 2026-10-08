"""
collector.py

Deterministic, read-only Kubernetes data collection.
No AI here — just three API calls:
  1. Pod object (status, spec, resources, probes)
  2. Events scoped to that pod
  3. Logs (previous run if the pod has restarted, else current)

This module never writes to the cluster. The ServiceAccount used to run
this tool should only ever be granted get/list/watch on pods, events,
and pods/log.
"""

from __future__ import annotations

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from src.context import pick_container_status


def load_client(in_cluster: bool = False) -> client.CoreV1Api:
    """Load kube config and return a CoreV1Api client.

    Prints which context is active so an engineer never accidentally
    investigates the wrong cluster.
    """
    if in_cluster:
        config.load_incluster_config()
        print("Reading from in-cluster context")
    else:
        config.load_kube_config()
        _, active_context = config.list_kube_config_contexts()
        print(f"Reading from context: {active_context['name']}")

    return client.CoreV1Api()


def collect(v1: client.CoreV1Api, name: str, namespace: str) -> dict:
    """Fetch pod, events and logs for a single pod.

    Returns a raw dict of Kubernetes objects. This is intentionally
    unprocessed — field extraction and redaction happen in context.py,
    not here.
    """
    pod = v1.read_namespaced_pod(name=name, namespace=namespace)

    events = v1.list_namespaced_event(
        namespace=namespace,
        field_selector=f"involvedObject.name={name}",
    ).items

    logs, logs_source = _fetch_logs(v1, name, namespace, pod)

    return {"pod": pod, "events": events, "logs": logs, "logs_source": logs_source}


def _fetch_logs(v1: client.CoreV1Api, name: str, namespace: str, pod) -> tuple[str, str]:
    """Fetch logs from the container under investigation.

    Returns (text, source), source being "previous", "current" or
    "unavailable". The crashed run's logs are what we want; HTTP 400
    means "no previous container", which is an expected state, so we
    fall back to current logs and say so. Any other API error (403,
    404, 5xx) is a real problem and propagates instead of being
    reported to the model as if it were evidence.
    """
    status = pick_container_status(pod)
    if status is None:
        return "<unavailable: container has not started>", "unavailable"

    kwargs = dict(name=name, namespace=namespace, container=status.name, tail_lines=200)

    if (status.restart_count or 0) > 0:
        try:
            return v1.read_namespaced_pod_log(previous=True, **kwargs), "previous"
        except ApiException as e:
            if e.status != 400:
                raise

    try:
        return v1.read_namespaced_pod_log(**kwargs), "current"
    except ApiException as e:
        if e.status == 400:  # e.g. container still creating / waiting
            return f"<unavailable: container has no logs yet ({e.reason})>", "unavailable"
        raise
