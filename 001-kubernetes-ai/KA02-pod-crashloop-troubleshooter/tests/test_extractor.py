from src.extractor import describe_state, extract_facts, pick_container_status
from tests.conftest import fake_event, make_pod, make_status


def test_picks_crashing_sidecar_not_first_container(crashing_sidecar_pod):
    assert pick_container_status(crashing_sidecar_pod).name == "istio-proxy"


def test_facts_come_from_the_crashing_container(crashing_sidecar_pod):
    facts = extract_facts(crashing_sidecar_pod, [])
    assert facts["container"] == "istio-proxy"
    assert facts["exit_code"] == 137 and facts["reason"] == "OOMKilled"
    assert facts["restart_count"] == 7
    assert facts["resource_limits"] == {"memory": "200Mi"}  # the sidecar's, not the app's
    assert facts["current_state"] == {"state": "waiting", "reason": "CrashLoopBackOff"}


def test_pod_with_no_container_statuses_yet():
    pod = make_pod([], containers=[])
    pod.status.container_statuses = None
    assert pick_container_status(pod) is None
    facts = extract_facts(pod, [])
    assert facts["container"] is None and facts["restart_count"] is None


def test_event_messages_are_redacted():
    pod = make_pod([make_status("app")])
    facts = extract_facts(pod, [fake_event("Failed", "pull failed token=abcdef123456")])
    assert "abcdef123456" not in facts["recent_events"][0]["message"]


def test_describe_state_none():
    assert describe_state(None)["state"] == "unknown"
