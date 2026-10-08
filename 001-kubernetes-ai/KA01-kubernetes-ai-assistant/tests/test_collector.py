from types import SimpleNamespace

import pytest
from kubernetes.client.exceptions import ApiException

from src.collector import _fetch_logs
from tests.conftest import make_pod, make_status


class FakeV1:
    def __init__(self, previous=None, current="cur"):
        self.previous, self.current, self.calls = previous, current, []

    def read_namespaced_pod_log(self, **kw):
        self.calls.append(kw)
        if kw.get("previous"):
            if isinstance(self.previous, Exception):
                raise self.previous
            return self.previous
        return self.current


def test_restarted_pod_prefers_previous_logs_of_picked_container(crashing_sidecar_pod):
    v1 = FakeV1(previous="crash logs")
    assert _fetch_logs(v1, "p", "ns", crashing_sidecar_pod) == ("crash logs", "previous")
    assert v1.calls[0]["container"] == "istio-proxy"


def test_400_on_previous_falls_back_to_current(crashing_sidecar_pod):
    v1 = FakeV1(previous=ApiException(status=400, reason="Bad Request"))
    assert _fetch_logs(v1, "p", "ns", crashing_sidecar_pod) == ("cur", "current")


@pytest.mark.parametrize("status", [403, 404, 500])
def test_real_errors_are_not_masked(crashing_sidecar_pod, status):
    v1 = FakeV1(previous=ApiException(status=status))
    with pytest.raises(ApiException):
        _fetch_logs(v1, "p", "ns", crashing_sidecar_pod)


def test_never_started_pod():
    pod = make_pod([make_status("app")])
    pod.status.container_statuses = None
    text, source = _fetch_logs(FakeV1(), "p", "ns", pod)
    assert source == "unavailable" and "unavailable" in text
