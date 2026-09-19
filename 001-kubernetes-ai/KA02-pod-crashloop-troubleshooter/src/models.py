"""Pydantic schema for the structured diagnosis returned by the LLM."""

from typing import List, Literal

from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    """Structured, validated output of the AI analysis step.

    This is the contract between the LLM and the rest of the system.
    If the model's response doesn't match this shape, it's rejected
    and the caller falls back to showing raw evidence instead
    (see troubleshooter.py / cli.py).
    """

    likely_cause: str = Field(..., description="Plain-language hypothesis for the failure")
    evidence: List[str] = Field(
        ..., description="Specific facts or log lines that support the hypothesis"
    )
    confidence: Literal["low", "medium", "high"] = Field(
        ..., description="How well the evidence supports the hypothesis"
    )
    recommended_next_step: str = Field(
        ..., description="One concrete, verifiable action for the engineer to take"
    )
