"""
Pipeline module: Orchestration layer.
Coordinates agents and services to execute complete workflows.

This is the ONLY module allowed to import from both agents and services.

Available orchestrators:
- build_video_package: Editorial brain orchestrator (agents only, no production)
- (future) produce_render_publish: Full production pipeline (agents + services)
- (future) scheduler: Automated job scheduling
"""

from yt_autopilot.pipeline.build_video_package import build_video_package

__all__ = [
    "build_video_package",
]
