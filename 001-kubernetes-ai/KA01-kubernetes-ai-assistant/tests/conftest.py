"""Builders for realistic Kubernetes objects — no cluster required."""

from types import SimpleNamespace

import pytest
from kubernetes import client as k


def make_status(name, restarts=0, terminated=None, waiting=None, running=False):
    return k.V1ContainerStatus(
        name=name, image="img", image_id="id", ready=False, restart_count=restarts,
        state=k.V1ContainerState(
            waiting=waiting, running=k.V1ContainerStateRunning() if running else None),
        last_state=k.V1ContainerState(terminated=terminated),
    )


def make_pod(statuses):
    return k.V1Pod(
        metadata=k.V1ObjectMeta(name="p", namespace="ns"),
        spec=k.V1PodSpec(containers=[
            k.V1Container(name=s.name, image="img",
                          resources=k.V1ResourceRequirements(limits={"memory": f"{i + 1}00Mi"}),
                          env=[k.V1EnvVar(name="DB_PASSWORD", value="hunter2")])
            for i, s in enumerate(statuses)
        ]),
        status=k.V1PodStatus(phase="Running", container_statuses=statuses),
    )


def fake_event(reason, message, ts):
    return SimpleNamespace(type="Warning", reason=reason, message=message,
                           last_timestamp=ts, event_time=None)


@pytest.fixture
def crashing_sidecar_pod():
    app = make_status("app", running=True)
    sidecar = make_status(
        "istio-proxy", restarts=7,
        terminated=k.V1ContainerStateTerminated(exit_code=137, reason="OOMKilled"),
        waiting=k.V1ContainerStateWaiting(reason="CrashLoopBackOff"),
    )
    return make_pod([app, sidecar])


class FakeResponse:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [SimpleNamespace(type="text", text=text)]
        self.stop_reason = stop_reason


class FakeClient:
    def __init__(self, text, stop_reason="end_turn"):
        self._resp = FakeResponse(text, stop_reason)
        self.messages = SimpleNamespace(create=lambda **kw: self._resp)
