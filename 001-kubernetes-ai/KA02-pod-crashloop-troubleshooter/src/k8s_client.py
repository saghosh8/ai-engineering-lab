"""Thin wrapper around the Kubernetes Python client for the data we need.

Everything here is pure retrieval — no interpretation, no AI. This module's
only job is to fetch pod status, events, and logs for a given pod.
"""

from typing import List, Optional, Tuple

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


def load_config(kubeconfig: Optional[str] = None, context: Optional[str] = None) -> None:
    """Load kube config from the given path/default location, else in-cluster.

    Only falls back to in-cluster config when no kubeconfig was asked for
    explicitly: silently ignoring a bad --kubeconfig path and talking to a
    different cluster than intended is the worse failure.
    """
    try:
        config.load_kube_config(config_file=kubeconfig, context=context)
    except Exception as kube_err:
        if kubeconfig:
            raise RuntimeError(f"Could not load kubeconfig {kubeconfig!r}: {kube_err}") from kube_err
        try:
            config.load_incluster_config()
        except Exception as cluster_err:
            raise RuntimeError(
                "No usable Kubernetes config: kubeconfig failed "
                f"({kube_err}) and in-cluster config failed ({cluster_err})"
            ) from cluster_err


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
             tail_lines: int = 100) -> Tuple[str, str]:
    """Fetch logs, preferring the previous (crashed) container run.

    Returns (text, source) where source is "previous" or "current", so the
    caller can tell the model which one it is looking at. Only HTTP 400
    ("no previous terminated container") triggers the fallback; auth,
    network and not-found errors propagate instead of being masked.
    """
    v1 = client.CoreV1Api()
    try:
        text = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            previous=True,
            tail_lines=tail_lines,
        )
        return text, "previous"
    except ApiException as e:
        if e.status != 400:
            raise
    text = v1.read_namespaced_pod_log(
        name=pod_name,
        namespace=namespace,
        container=container,
        tail_lines=tail_lines,
    )
    return text, "current"
