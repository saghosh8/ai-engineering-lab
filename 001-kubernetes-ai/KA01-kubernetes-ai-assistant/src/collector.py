"""
collector.py

Deterministic, read-only Kubernetes data collection.
No AI here — just three API calls:
  1. Pod object (status, spec, resources, probes)
  2. Events scoped to that pod
  3. Logs (current, and previous if the pod has restarted)

This module never writes to the cluster. The ServiceAccount used to run
this tool should only ever be granted get/list/watch on pods, events,
and pods/log.
"""

from __future__ import annotations

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


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

    logs = _fetch_logs(v1, name, namespace, pod)

    return {"pod": pod, "events": events, "logs": logs}


def _fetch_logs(v1: client.CoreV1Api, name: str, namespace: str, pod) -> str:
    """Fetch logs, preferring the previous container instance on restart.

    A pod that has never restarted has no previous container, and the
    API returns HTTP 400 for that case. That is an expected state, not
    a failure — we record it and move on rather than raising.
    """
    if not pod.status.container_statuses:
        return "<unavailable: container has not started>"

    status = pod.status.container_statuses[0]
    want_previous = status.restart_count > 0

    try:
        return v1.read_namespaced_pod_log(
            name=name,
            namespace=namespace,
            tail_lines=200,
            previous=want_previous,
        )
    except ApiException as e:
        return f"<unavailable: previous container not found ({e.status})>"
