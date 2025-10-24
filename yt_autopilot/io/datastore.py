"""
Datastore Module: Local persistence for video packages and metrics.

This module handles storage of video packages, upload results, and analytics
in a local JSONL database for historical tracking and analysis.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from yt_autopilot.core.schemas import ReadyForFactory, UploadResult, VideoMetrics
from yt_autopilot.core.config import get_config
from yt_autopilot.core.logger import logger


def _get_datastore_path() -> Path:
    """
    Returns path to the datastore file.

    Returns:
        Path to data/records.jsonl
    """
    config = get_config()
    data_dir = config["PROJECT_ROOT"] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "records.jsonl"


def save_video_package(
    ready: ReadyForFactory,
    scene_paths: List[str],
    voiceover_path: str,
    final_video_path: str,
    upload_result: UploadResult
) -> None:
    """
    Saves complete video package to datastore.

    Stores all information about a produced video including:
    - Editorial package (plan, script, visuals, publishing)
    - File paths (scenes, voiceover, final video)
    - Upload result (video ID, publish time)
    - Timestamp

    Args:
        ready: Editorial package that was produced
        scene_paths: List of scene video file paths
        voiceover_path: Path to voiceover audio file
        final_video_path: Path to final assembled video
        upload_result: Result from YouTube upload

    Example:
        >>> from yt_autopilot.core.schemas import (
        ...     ReadyForFactory, VideoPlan, VideoScript,
        ...     VisualPlan, PublishingPackage, UploadResult
        ... )
        >>> # ... create instances ...
        >>> save_video_package(
        ...     ready=package,
        ...     scene_paths=["scene1.mp4"],
        ...     voiceover_path="voice.wav",
        ...     final_video_path="final.mp4",
        ...     upload_result=result
        ... )
    """
    logger.info("Saving video package to datastore...")

    datastore_path = _get_datastore_path()

    record = {
        "saved_at": datetime.now().isoformat(),
        "youtube_video_id": upload_result.youtube_video_id,
        "status": ready.status,
        "title": ready.publishing.final_title,
        "publish_at": upload_result.published_at,
        "video_plan": ready.video_plan.model_dump(),
        "script": ready.script.model_dump(),
        "visuals": ready.visuals.model_dump(),
        "publishing": ready.publishing.model_dump(),
        "files": {
            "scene_paths": scene_paths,
            "voiceover_path": voiceover_path,
            "final_video_path": final_video_path
        },
        "upload_result": upload_result.model_dump()
    }

    # Append to JSONL file
    with open(datastore_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"✓ Video package saved to {datastore_path}")
    logger.info(f"  Video ID: {upload_result.youtube_video_id}")
    logger.info(f"  Title: '{ready.publishing.final_title}'")


def list_published_videos() -> List[Dict[str, Any]]:
    """
    Returns list of all published/scheduled videos.

    Returns:
        List of video records with basic metadata

    Example:
        >>> videos = list_published_videos()
        >>> for video in videos:
        ...     print(f"{video['youtube_video_id']}: {video['title']}")
        mock_video_123: Test Video
    """
    logger.info("Listing published videos from datastore...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.warning("Datastore file does not exist yet")
        return []

    videos = []
    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())
            videos.append({
                "youtube_video_id": record["youtube_video_id"],
                "title": record["title"],
                "publish_at": record["publish_at"],
                "saved_at": record["saved_at"],
                "status": record["status"]
            })

    logger.info(f"✓ Found {len(videos)} videos in datastore")
    return videos


def save_metrics(video_id: str, metrics: VideoMetrics) -> None:
    """
    Saves analytics metrics for a video.

    Stores metrics in a separate metrics file for time-series analysis.

    Args:
        video_id: YouTube video ID
        metrics: Performance metrics from YouTube Analytics

    Example:
        >>> from yt_autopilot.core.schemas import VideoMetrics
        >>> metrics = VideoMetrics(
        ...     video_id="abc123",
        ...     views=1000,
        ...     watch_time_seconds=5000,
        ...     average_view_duration_seconds=5.0,
        ...     ctr=0.05
        ... )
        >>> save_metrics("abc123", metrics)
    """
    logger.info(f"Saving metrics for video {video_id}...")

    config = get_config()
    data_dir = config["PROJECT_ROOT"] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = data_dir / "metrics.jsonl"

    record = {
        "video_id": video_id,
        "collected_at": metrics.collected_at_iso,
        "views": metrics.views,
        "watch_time_seconds": metrics.watch_time_seconds,
        "average_view_duration_seconds": metrics.average_view_duration_seconds,
        "ctr": metrics.ctr
    }

    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"✓ Metrics saved to {metrics_path}")
    logger.info(f"  Views: {metrics.views:,}, CTR: {metrics.ctr:.2%}")


def get_metrics_history(video_id: str) -> List[VideoMetrics]:
    """
    Retrieves historical metrics for a video.

    Args:
        video_id: YouTube video ID

    Returns:
        List of VideoMetrics ordered by collection time

    Example:
        >>> history = get_metrics_history("abc123")
        >>> print(f"Collected {len(history)} metric snapshots")
        Collected 5 metric snapshots
    """
    logger.info(f"Retrieving metrics history for video {video_id}...")

    config = get_config()
    metrics_path = config["PROJECT_ROOT"] / "data" / "metrics.jsonl"

    if not metrics_path.exists():
        logger.warning("Metrics file does not exist yet")
        return []

    history = []
    with open(metrics_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())
            if record["video_id"] == video_id:
                metrics = VideoMetrics(
                    video_id=record["video_id"],
                    views=record["views"],
                    watch_time_seconds=record["watch_time_seconds"],
                    average_view_duration_seconds=record["average_view_duration_seconds"],
                    ctr=record["ctr"],
                    collected_at_iso=record["collected_at"]
                )
                history.append(metrics)

    logger.info(f"✓ Found {len(history)} metric snapshots")
    return history
