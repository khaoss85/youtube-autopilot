"""
I/O module: Data persistence and exports.
Handles local storage (JSONL) and historical data management.

Available modules:
- datastore: Save and retrieve video packages and metrics
- exports: Export data to CSV for analysis

Production States:
- HUMAN_REVIEW_PENDING: Video assets generated, waiting for human approval
- SCHEDULED_ON_YOUTUBE: Video uploaded and scheduled on YouTube
"""

from yt_autopilot.io.datastore import (
    list_published_videos,
    save_metrics,
    get_metrics_history,
    save_draft_package,
    get_draft_package,
    list_scheduled_videos,
    list_pending_review
)
from yt_autopilot.io.exports import (
    export_report_csv,
    export_metrics_timeseries_csv,
    export_content_package_to_markdown
)

__all__ = [
    # Datastore - content strategy focus
    "list_published_videos",
    "save_metrics",
    "get_metrics_history",
    # Datastore - script review workflow (Phase 1 refactor)
    "save_draft_package",
    "get_draft_package",
    "list_scheduled_videos",
    "list_pending_review",
    # Exports - Analytics
    "export_report_csv",
    "export_metrics_timeseries_csv",
    # Exports - Content packages (Phase 1 refactor)
    "export_content_package_to_markdown",
]
