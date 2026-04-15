"""Validation output model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Violation(BaseModel):
    rule: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
