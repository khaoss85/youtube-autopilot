"""
Pipeline module: Orchestration layer.
Coordinates agents to execute content strategy workflows.

Content Strategy Focus (Phase 1 Refactor):
- This module focuses on editorial strategy and content package generation
- Video production has been removed (use external AI tools: RunwayML, Luma, Pika)
- Output: Markdown files with scene-by-scene prompts for manual production

Available modules:
- build_video_package: Editorial brain orchestrator (AI-driven strategy)
"""

from yt_autopilot.pipeline.build_video_package import build_video_package

__all__ = [
    "build_video_package",
]
