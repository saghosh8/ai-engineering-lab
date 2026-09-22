# KA02 — Pod CrashLoop Troubleshooter

Give an LLM read-only access to pod status, events and logs and let it
correlate the structured signals with the free-text log evidence into a
single, confidence-rated root-cause hypothesis — evidence and
interpretation kept clearly separate.

[![Substack](https://img.shields.io/badge/%F0%9F%93%96%20READ%20THE%20ARTICLE-KA02-F5EEDC?style=for-the-badge&labelColor=1237A)](https://techworldwithsahana.substack.com/p/building-an-ai-troubleshooting-assistant-for-kubernetes)

Understand the concepts behind this build: *Your Pod Just Crashed for the Fifth Time — Here's How to Get an AI to Explain Why.*

[![KA02 architecture](https://github.com/saghosh8/ai-engineering-lab/raw/main/001-kubernetes-ai/images/KA02.jpg)](/saghosh8/ai-engineering-lab/blob/main/001-kubernetes-ai/images/KA02.jpg)

## What this is

A CLI tool. You give it a pod, it gives you a structured diagnosis.

```
$ python -m src.cli --namespace payments --pod payment-worker-7d9f8c-xk2p1
```

- **Input:** pod name + namespace
- **Processing (deterministic):** three read-only Kubernetes API calls
  (pod, events, logs), field extraction (exit code, restart count,
  reason, resource limits), log redaction
- **AI (one call):** a single hypothesis with cited evidence and a
  confidence level, returned as validated JSON
- **Output:** a report that visually separates observed facts from
  model interpretation

No agent. No tool calling. No RAG. No writes to the cluster.

## Project layout

```
KA02-pod-crashloop-troubleshooter/
├── src/
│   ├── k8s_client.py     # Kubernetes API calls (read-only)
│   ├── extractor.py      # deterministic fact extraction
│   ├── redactor.py       # secret/PII redaction
│   ├── llm_client.py     # LLM call, prompt, schema hint
│   ├── models.py         # Pydantic schema for the diagnosis
│   ├── troubleshooter.py # pipeline orchestration
│   └── cli.py            # entry point
├── examples/              # sample evidence for offline testing
│   ├── sample_facts.json
│   ├── sample_logs.txt
│   └── demo.py
├── requirements.txt
└── .env.example
```

## Setup

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY
```

Requires a valid kubeconfig context pointing at the cluster you want to
investigate (`kubectl config current-context` to check).

## Usage

```
python -m src.cli --namespace <namespace> --pod <pod-name>

# control how many log lines are pulled
python -m src.cli --namespace <namespace> --pod <pod-name> --tail-lines 200

# point at a specific kubeconfig
python -m src.cli --namespace <namespace> --pod <pod-name> --kubeconfig ./my-kubeconfig
```

## Testing without a live cluster

The `examples/` folder contains a saved evidence bundle (facts + logs)
from a real failure mode (database connection timeout). Use it to
iterate on the prompt in `llm_client.py` without needing a cluster:

```
python examples/demo.py
```

This still makes a real call to the Anthropic API — it skips the
Kubernetes dependency, not the LLM one. `ANTHROPIC_API_KEY` must be set.

## Required RBAC (real cluster usage)

This tool should never run with more access than it needs:

```
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-troubleshooter-reader
  namespace: payments
rules:
  - apiGroups: [""]
    resources: ["pods", "events"]
    verbs: ["get", "list"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
```

No `create`, `update`, `patch` or `delete` — by construction, not by
prompt instruction.

## Known limitations

- Single-pod scope only. Doesn't look at Deployment/ReplicaSet history
  or sibling pods in the same failure.
- Single LLM call, no retries with alternate prompts, no multi-step
  investigation.
- Redaction is regex-based (tokens, connection-string passwords, AWS
  keys, generic secrets, emails). Extend the patterns in
  `redactor.py` for your own naming conventions before pointing this
  at anything real.
- No auto-remediation of any kind — output is advisory only, by design.

---

## ⭐ Support

If you found this repository useful:

[![Stars](https://img.shields.io/github/stars/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&label=STAR%20THIS%20REPO)](https://github.com/saghosh8/ai-engineering-lab)
[![Forks](https://img.shields.io/github/forks/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&label=FORK)](https://github.com/saghosh8/ai-engineering-lab/fork)
