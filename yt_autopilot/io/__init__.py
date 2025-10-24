"""
I/O module: Data persistence and exports.
Handles local storage (JSONL) and historical data management.

Available modules:
- datastore: Save and retrieve video packages and metrics
- exports: Export data to CSV for analysis
"""

from yt_autopilot.io.datastore import (
    save_video_package,
    list_published_videos,
    save_metrics,
    get_metrics_history
)
from yt_autopilot.io.exports import (
    export_report_csv,
    export_metrics_timeseries_csv
)

__all__ = [
    # Datastore
    "save_video_package",
    "list_published_videos",
    "save_metrics",
    "get_metrics_history",
    # Exports
    "export_report_csv",
    "export_metrics_timeseries_csv",
]
