# KA02 — AI Pod Troubleshooter

Investigate a `CrashLoopBackOff` pod using pod status, events, and logs — with a single AI call doing the correlation work an engineer would otherwise do by hand.

Companion project to the AIxDevOps newsletter article *"Your Pod Just Crashed for the Fifth Time — Here's How to Get an AI to Explain Why."*

## What this is

A small, single-shot diagnostic tool. It does **not** auto-fix anything, does not loop, and does not use RAG or tool calling. It:

1. Collects pod status, events, and logs from the Kubernetes API (deterministic)
2. Extracts the structured facts that matter — exit code, restart count, reason, resource limits (deterministic)
3. Redacts secrets/PII from log text before it leaves the cluster (deterministic)
4. Sends the facts + redacted log excerpt to an LLM for a single diagnosis call (AI)
5. Validates the response against a strict schema, falling back to raw evidence on failure (deterministic)
6. Prints a structured report for a human to verify

```
kubectl/API → extract facts → redact logs → LLM (one call) → validate → report
```

The AI never sees raw exit codes as anything but ground truth, and it never triggers any action in the cluster. It proposes a hypothesis; you verify it.

## Project structure

```
KA02-pod-crashloop-troubleshooter/
├── src/
│   ├── k8s_client.py     # Kubernetes API wrapper (pod, events, logs)
│   ├── extractor.py      # Deterministic fact extraction
│   ├── redactor.py       # Deterministic secret/PII redaction
│   ├── llm_client.py     # The single LLM call + prompt + schema hint
│   ├── models.py         # Pydantic schema for the validated diagnosis
│   ├── troubleshooter.py # Orchestrates the full pipeline
│   └── cli.py            # Command-line entrypoint
├── examples/
│   ├── sample_facts.json # Example deterministic facts
│   ├── sample_logs.txt   # Example log excerpt
│   └── demo.py           # Runs the diagnosis step with no live cluster needed
├── requirements.txt
└── .env.example
```

## Setup

```bash
git clone https://github.com/saghosh8/ai-engineering-lab.git
cd ai-engineering-lab/001-kubernetes-ai/KA02-pod-crashloop-troubleshooter

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

## Usage

### Try it without a cluster (demo mode)

Uses the sample facts/logs in `examples/` and makes one real LLM call:

```bash
python examples/demo.py
```

### Run it against a real pod

Requires a working kubeconfig with read access to pods, pod/log, and events in the target namespace:

```bash
python -m src.cli --namespace payments --pod payment-worker-7d9f8c-xk2p1
```

Optional flags:

```
--tail-lines N       Number of log lines to fetch (default: 100)
--kubeconfig PATH    Path to a specific kubeconfig file
```

### Example output

```
============================================================
EVIDENCE (deterministic)
============================================================
{
  "pod_name": "payment-worker-7d9f8c-xk2p1",
  "restart_count": 6,
  "exit_code": 1,
  "reason": "Error",
  ...
}

============================================================
AI DIAGNOSIS (hypothesis — verify before acting)
============================================================
Likely cause     : Application cannot reach the database and exits after retry exhaustion
Confidence       : MEDIUM
Evidence:
  - exit_code=1 with reason Error
  - repeated OperationalError connection timeouts to db-primary
  - BackOff event confirms repeated restarts
Next step        : Verify db-primary Service/Endpoints and network policy from this namespace
```

## Required RBAC (real cluster usage)

The identity running this tool needs read-only access to pods, pod logs, and events in the target namespace — nothing more:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-troubleshooter-reader
  namespace: payments
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/log", "events"]
    verbs: ["get", "list"]
```

## What's deterministic vs. what's AI

| Step | Deterministic | AI |
|---|---|---|
| Fetching pod/events/logs | ✅ | |
| Extracting exit code, restart count, reason | ✅ | |
| Redacting secrets/PII | ✅ | |
| Correlating log text with structured signals into a hypothesis | | ✅ |
| Validating the response shape | ✅ | |

## Limitations (by design)

- Single LLM call, no retries with alternate prompts, no multi-step investigation
- Redaction is regex-based and intentionally simple — not a substitute for a real secrets scanner in production
- No auto-remediation of any kind — output is advisory only
- Confidence is self-reported by the model, not independently calibrated

See the companion article's "Production Considerations" section for what changes before this goes anywhere near production.

## License

MIT — use freely, no warranty. This is a learning/reference project, not a production tool.
