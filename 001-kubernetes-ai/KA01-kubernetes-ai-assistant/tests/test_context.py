from src.context import build_evidence, truncate
from tests.conftest import fake_event


def test_truncate_keeps_both_ends():
    text = "\n".join(f"line{i}" for i in range(1000))
    out = truncate(text, head=2, tail=3)
    assert out.splitlines()[:2] == ["line0", "line1"]
    assert out.splitlines()[-1] == "line999" and "995 lines omitted" in out
    assert truncate("a\nb") == "a\nb"


def test_evidence_targets_crashing_sidecar_and_redacts(crashing_sidecar_pod):
    raw = {
        "pod": crashing_sidecar_pod,
        "events": [fake_event("B", "second token=abcdef123456", "2026-01-02"),
                   fake_event("A", "first", "2026-01-01")],
        "logs": "connect postgres://u:hunter2@db/x failed\npassword=hunter2",
        "logs_source": "previous",
    }
    ev = build_evidence(raw)
    assert ev["container"] == "istio-proxy"
    assert ev["last_terminated"] == {"exit_code": 137, "reason": "OOMKilled"}
    assert ev["current_state"] == {"state": "waiting", "reason": "CrashLoopBackOff"}
    assert ev["resources"]["limits"] == {"memory": "200Mi"}
    assert ev["logs_source"] == "previous"
    # events sorted oldest -> newest, secrets gone from logs AND events
    assert ev["events"][0].endswith("first") and "abcdef123456" not in ev["events"][1]
    assert "hunter2" not in ev["logs"]
    assert ev["env_names"] == ["DB_PASSWORD=<redacted>"]
