"""
Exports Module: Export data to various formats for analysis.

This module handles exporting datastore data to CSV, Excel, or other
formats for external analysis and reporting.
"""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from yt_autopilot.core.config import get_config
from yt_autopilot.core.logger import logger
from yt_autopilot.io.datastore import list_published_videos, get_metrics_history


def export_report_csv(csv_path: Optional[str] = None) -> str:
    """
    Exports video performance report to CSV.

    Creates a CSV file with columns:
    - youtube_video_id: YouTube video ID
    - title: Video title
    - publish_at: Scheduled/actual publish time
    - views_latest: Most recent view count
    - ctr_latest: Most recent click-through rate
    - avg_view_duration_latest: Most recent average view duration
    - watch_time_latest: Most recent total watch time

    Args:
        csv_path: Optional custom path for CSV file.
                  If None, uses ./data/report.csv

    Returns:
        Path to generated CSV file

    Example:
        >>> report_path = export_report_csv()
        >>> print(f"Report saved to: {report_path}")
        Report saved to: ./data/report.csv
    """
    logger.info("Exporting performance report to CSV...")

    if csv_path is None:
        config = get_config()
        data_dir = config["PROJECT_ROOT"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        csv_path = str(data_dir / "report.csv")

    # Get all published videos
    videos = list_published_videos()

    if not videos:
        logger.warning("No videos found in datastore - creating empty report")

    # Prepare report data
    report_rows: List[Dict[str, Any]] = []

    for video in videos:
        video_id = video["youtube_video_id"]

        # Get latest metrics for this video
        metrics_history = get_metrics_history(video_id)

        if metrics_history:
            latest_metrics = metrics_history[-1]  # Most recent
            views = latest_metrics.views
            ctr = latest_metrics.ctr
            avg_duration = latest_metrics.average_view_duration_seconds
            watch_time = latest_metrics.watch_time_seconds
        else:
            # No metrics yet
            views = 0
            ctr = 0.0
            avg_duration = 0.0
            watch_time = 0.0

        report_rows.append({
            "youtube_video_id": video_id,
            "title": video["title"],
            "publish_at": video["publish_at"],
            "status": video["status"],
            "views_latest": views,
            "ctr_latest": f"{ctr:.4f}",
            "avg_view_duration_latest": f"{avg_duration:.2f}",
            "watch_time_latest": f"{watch_time:.2f}"
        })

    # Write CSV
    if report_rows:
        fieldnames = [
            "youtube_video_id",
            "title",
            "publish_at",
            "status",
            "views_latest",
            "ctr_latest",
            "avg_view_duration_latest",
            "watch_time_latest"
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(report_rows)

        logger.info(f"✓ Report exported to {csv_path}")
        logger.info(f"  Videos: {len(report_rows)}")
        logger.info(f"  Columns: {len(fieldnames)}")
    else:
        # Create empty CSV with headers
        fieldnames = [
            "youtube_video_id",
            "title",
            "publish_at",
            "status",
            "views_latest",
            "ctr_latest",
            "avg_view_duration_latest",
            "watch_time_latest"
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

        logger.info(f"✓ Empty report created at {csv_path}")

    return csv_path


def export_metrics_timeseries_csv(video_id: str, csv_path: Optional[str] = None) -> str:
    """
    Exports time-series metrics for a specific video to CSV.

    Args:
        video_id: YouTube video ID
        csv_path: Optional custom path for CSV file

    Returns:
        Path to generated CSV file

    Example:
        >>> path = export_metrics_timeseries_csv("abc123")
        >>> print(f"Timeseries saved to: {path}")
        Timeseries saved to: ./data/metrics_abc123.csv
    """
    logger.info(f"Exporting metrics timeseries for video {video_id}...")

    if csv_path is None:
        config = get_config()
        data_dir = config["PROJECT_ROOT"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        csv_path = str(data_dir / f"metrics_{video_id}.csv")

    # Get metrics history
    metrics_history = get_metrics_history(video_id)

    if not metrics_history:
        logger.warning(f"No metrics found for video {video_id}")
        return csv_path

    # Write CSV
    fieldnames = [
        "collected_at",
        "views",
        "watch_time_seconds",
        "average_view_duration_seconds",
        "ctr"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for metrics in metrics_history:
            writer.writerow({
                "collected_at": metrics.collected_at_iso,
                "views": metrics.views,
                "watch_time_seconds": f"{metrics.watch_time_seconds:.2f}",
                "average_view_duration_seconds": f"{metrics.average_view_duration_seconds:.2f}",
                "ctr": f"{metrics.ctr:.4f}"
            })

    logger.info(f"✓ Timeseries exported to {csv_path}")
    logger.info(f"  Data points: {len(metrics_history)}")

    return csv_path
