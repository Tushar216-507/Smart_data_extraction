"""
pipelines/pipeline_context.py

Shared context passed to every pipeline stage.

Instead of passing 6+ parameters to each stage function,
the pipeline creates one PipelineContext and passes it
everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from workspace.workspace_manager import WorkspaceManager
from knowledge.llm.provider import LLMProvider
from knowledge.billing.usage_tracker import UsageTracker


@dataclass
class PipelineContext:
    """
    Immutable bag of shared resources for a single pipeline run.

    Every stage receives this instead of individual arguments.
    """

    university_url: str
    workspace: WorkspaceManager
    llm_provider: LLMProvider
    usage_tracker: UsageTracker

    program_limit: Optional[int] = None
    continue_on_error: bool = False
    verbose: bool = False
