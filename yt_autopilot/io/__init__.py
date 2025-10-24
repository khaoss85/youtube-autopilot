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
    save_video_package,
    list_published_videos,
    save_metrics,
    get_metrics_history,
    save_draft_package,
    get_draft_package,
    mark_as_scheduled,
    list_scheduled_videos
)
from yt_autopilot.io.exports import (
    export_report_csv,
    export_metrics_timeseries_csv
)

__all__ = [
    # Datastore - legacy/general
    "save_video_package",
    "list_published_videos",
    "save_metrics",
    "get_metrics_history",
    # Datastore - production workflow with human gate
    "save_draft_package",
    "get_draft_package",
    "mark_as_scheduled",
    "list_scheduled_videos",
    # Exports
    "export_report_csv",
    "export_metrics_timeseries_csv",
]
