"""
Pipeline module: Orchestration layer.
Coordinates agents and services to execute complete workflows.

This is the ONLY module allowed to import from both agents and services.

Available modules:
- build_video_package: Editorial brain orchestrator (agents only)
- produce_render_publish: Full production pipeline with human gate (agents + services)
- tasks: Reusable tasks for scheduler automation

Production States:
- HUMAN_REVIEW_PENDING: Video generated, awaiting human approval
- SCHEDULED_ON_YOUTUBE: Video uploaded and scheduled

Human Gate:
- produce_render_assets() generates drafts (can be automated)
- publish_after_approval() uploads to YouTube (MUST be manual)
"""

from yt_autopilot.pipeline.build_video_package import build_video_package
from yt_autopilot.pipeline.produce_render_publish import (
    produce_render_assets,
    publish_after_approval
)
from yt_autopilot.pipeline.tasks import (
    task_generate_assets_for_review,
    task_publish_after_human_ok,
    task_collect_metrics
)

__all__ = [
    # Editorial brain (Step 03)
    "build_video_package",
    # Full production pipeline (Step 05)
    "produce_render_assets",
    "publish_after_approval",
    # Reusable tasks (Step 05, for scheduler in Step 06)
    "task_generate_assets_for_review",
    "task_publish_after_human_ok",
    "task_collect_metrics",
]
