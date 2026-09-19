"""Thin wrapper around the Kubernetes Python client for the data we need.

Everything here is pure retrieval — no interpretation, no AI. This module's
only job is to fetch pod status, events, and logs for a given pod.
"""

from typing import List, Optional

from kubernetes import client, config


def load_config(kubeconfig: Optional[str] = None, context: Optional[str] = None) -> None:
    """Load kube config from the default location, a given path, or in-cluster."""
    try:
        config.load_kube_config(config_file=kubeconfig, context=context)
    except Exception:
        # Falls back to in-cluster config if running inside a pod
        config.load_incluster_config()


def get_pod(namespace: str, pod_name: str) -> client.V1Pod:
    v1 = client.CoreV1Api()
    return v1.read_namespaced_pod(name=pod_name, namespace=namespace)


def get_events(namespace: str, pod_name: str, limit: int = 10) -> List:
    v1 = client.CoreV1Api()
    events = v1.list_namespaced_event(
        namespace=namespace,
        field_selector=f"involvedObject.name={pod_name}",
    )
    items = sorted(events.items, key=lambda e: str(e.last_timestamp or e.event_time or ""))
    return items[-limit:]


def get_logs(namespace: str, pod_name: str, container: Optional[str] = None,
             tail_lines: int = 100) -> str:
    """Fetch logs, preferring the previous (crashed) container run if it exists,
    falling back to the current container's logs otherwise.
    """
    v1 = client.CoreV1Api()
    try:
        return v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            previous=True,
            tail_lines=tail_lines,
        )
    except client.exceptions.ApiException:
        return v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
        )
