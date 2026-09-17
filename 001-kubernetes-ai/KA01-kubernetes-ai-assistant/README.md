# 001 — Kubernetes AI Assistant

Give an LLM controlled, read-only access to `kubectl` output and let it
correlate pod status, events and logs into ranked troubleshooting
hypotheses — evidence and interpretation kept clearly separate.

📖 Read the article to understand the concepts behind this build: [Your Pod Keeps Crashing. What If an LLM Could Read the Logs Before You Do? — KA01](https://techworldwithsahana.substack.com/p/d75a91ad-33ea-4458-a10d-7231e9673801?postPreview=free&updated=2026-09-16T17%3A24%3A05.043Z&audience=everyone&free_preview=false&freemail=true)

![KA01 architecture](../images/KA01)

## What this is

A CLI tool. You give it a pod, it gives you a structured investigation.

```
$ python -m src.cli investigate checkout-api-7d9f8b6c5-xk2mz -n payments
```

- **Input:** pod name + namespace
- **Processing (deterministic):** three read-only Kubernetes API calls,
  field extraction, log truncation, secret redaction
- **AI (one call):** ranked hypotheses with cited evidence, returned as
  validated JSON
- **Output:** a report that visually separates observed facts from
  model interpretation

No agent. No tool calling. No RAG. No writes to the cluster.

## Project layout

```
001-kubernetes-ai/
├── src/
│   ├── collector.py    # Kubernetes API calls (read-only)
│   ├── context.py      # field extraction, redaction, truncation
│   ├── analyzer.py     # LLM call, schema validation, evidence check
│   └── cli.py           # entry point
├── examples/            # saved evidence bundles for offline testing
│   ├── oomkilled.json
│   ├── imagepullbackoff.json
│   └── probe-failure.json
├── requirements.txt
└── .env.example
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY
```

Requires a valid kubeconfig context pointing at the cluster you want to
investigate (`kubectl config current-context` to check).

## Usage

```bash
python -m src.cli investigate <pod-name> -n <namespace>

# also save the evidence bundle to disk
python -m src.cli investigate <pod-name> -n <namespace> --save-evidence ./evidence.json

# inside the cluster (uses in-cluster ServiceAccount instead of local kubeconfig)
python -m src.cli investigate <pod-name> -n <namespace> --in-cluster
```

## Testing without a live cluster

The `examples/` folder contains saved evidence bundles from three real
failure modes (OOMKilled, ImagePullBackOff, failed liveness probe).
Use these to iterate on the prompt in `analyzer.py` without needing a
cluster or burning API calls against live data:

```python
import json
from src.analyzer import call_llm, verify_evidence_grounding

evidence = json.load(open("examples/oomkilled.json"))
analysis = call_llm(evidence)
analysis = verify_evidence_grounding(analysis, evidence)
print(analysis.summary)
```

## Required RBAC (in-cluster deployment)

This tool should never run with more access than it needs:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: k8s-assist-reader
rules:
  - apiGroups: [""]
    resources: ["pods", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: [""]
    resources: ["pods/log"]
    verbs: ["get"]
```

No `create`, `update`, `patch` or `delete` — by construction, not by
prompt instruction.

## Known limitations

- Single-pod scope only. Doesn't (yet) look at Deployment/ReplicaSet
  history or sibling pods.
- No caching — repeated investigations of the same pod re-call the
  model. See "How This Could Evolve" in the newsletter for the
  production-hardening path.
- Redaction is keyword-based (`PASSWORD`, `SECRET`, `TOKEN`, `KEY`,
  `CREDENTIAL`, `DSN`). Extend `REDACT_KEYWORDS` in `context.py` for
  your own naming conventions before pointing this at anything real.

---

## ⭐ Support

If you found this repository useful:

<a href="https://github.com/saghosh8/ai-engineering-lab">
  <img src="https://img.shields.io/github/stars/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&logoColor=white&label=STAR%20THIS%20REPO" />
</a>
<a href="https://github.com/saghosh8/ai-engineering-lab/fork">
  <img src="https://img.shields.io/github/forks/saghosh8/ai-engineering-lab?style=for-the-badge&logo=github&label=FORK" />
</a>

---
