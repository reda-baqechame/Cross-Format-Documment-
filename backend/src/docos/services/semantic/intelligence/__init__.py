"""Typed document intelligence — the IDP layer over the canonical model.

``analyze(doc)`` returns a ``DocumentInsight``: the fields that matter for the
detected document kind plus actionable checks that verify it does its job.
"""

from __future__ import annotations

from docos.services.semantic.intelligence.analyzers import analyze
from docos.services.semantic.intelligence.base import (
    DocumentInsight,
    InsightCheck,
    InsightField,
)

__all__ = ["analyze", "DocumentInsight", "InsightCheck", "InsightField"]
