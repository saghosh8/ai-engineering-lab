"""Step 7: turn the result into a report people (or scripts) can use.

The Markdown report keeps what the log *shows* (rule-based evidence)
visibly separate from what the model *thinks* (interpretation), so a
reader can always see which part is a fact.
"""

import json
from dataclasses import asdict

from src.analyzer import AnalysisResult
from src.signatures import BY_CATEGORY

CI_NAMES = {"github-actions": "GitHub Actions", "jenkins": "Jenkins", "unknown": "unknown CI"}


def _label(category: str) -> str:
    return BY_CATEGORY[category].label if category in BY_CATEGORY else "Cause not identified"


def render_markdown(r: AnalysisResult) -> str:
    out = ["## CI failure analysis"]
    if not r.failed:
        out.append("")
        out.extend(r.notes or ["No failure found in this log."])
        return "\n".join(out) + "\n"

    confidence = f", confidence **{r.diagnosis['confidence']}**" if r.diagnosis else ""
    out += ["", f"**Likely failure:** {_label(r.category)}{confidence}",
            f"**CI:** {CI_NAMES.get(r.ci, r.ci)} · **Failed step:** {r.step or 'not detected'}"]
    if r.diagnosis and r.diagnosis["flaky_suspected"]:
        out.append("**Possibly flaky:** this kind of failure often passes on retry.")

    out += ["", "### What the log shows (rule-based)"]
    if r.candidates:
        for c in r.candidates[:3]:
            out.append(f"- **{c.label}** ({c.matches} matching line{'s' if c.matches != 1 else ''})")
            out.extend(f"  - `L{e.line_no}` {e.text}" for e in c.evidence)
    else:
        out.append("- No known failure pattern matched.")

    out += ["", "### Interpretation (AI)"]
    if r.diagnosis:
        d = r.diagnosis
        out += [f"**Likely cause:** {d['likely_cause']}"]
        if d["evidence"]:
            out += ["", "**Evidence from the log:**"] + [f"- `{e}`" for e in d["evidence"]]
        if d["next_steps"]:
            out += ["", "**Next steps:**"] + [f"{i}. {s}" for i, s in enumerate(d["next_steps"], 1)]
    else:
        out.append(f"Not available: {r.llm_skipped_reason or 'no model output'}. "
                   "The result above is rule-based only.")
    if r.notes:
        out += [""] + [f"> {n}" for n in r.notes]
    out += ["", "_AI-assisted. Verify against the full log before acting._"]
    return "\n".join(out) + "\n"


def render_json(r: AnalysisResult) -> str:
    data = {
        "ci": r.ci, "failed_step": r.step, "log_lines": r.line_count, "failed": r.failed,
        "category": r.category if r.failed else None,
        "candidates": [asdict(c) for c in r.candidates],
        "diagnosis": r.diagnosis, "llm_used": r.llm_used,
        "llm_skipped_reason": r.llm_skipped_reason, "notes": r.notes,
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
