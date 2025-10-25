"""
Datastore Module: Local persistence for video packages and metrics.

This module handles storage of video packages, upload results, and analytics
in a local JSONL database for historical tracking and analysis.

Production States:
- HUMAN_REVIEW_PENDING: Video assets generated, waiting for human approval
- SCHEDULED_ON_YOUTUBE: Video uploaded and scheduled on YouTube
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
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


def save_draft_package(
    ready: ReadyForFactory,
    scene_paths: List[str],
    voiceover_path: str,
    final_video_path: str,
    thumbnail_path: str,
    publish_datetime_iso: str,
    llm_raw_script: Optional[str] = None,
    final_script: Optional[str] = None
) -> str:
    """
    Saves a draft video package pending human review.

    Creates a record with production_state="HUMAN_REVIEW_PENDING" and
    generates a unique video_internal_id for future reference.

    This function is called AFTER physical assets are generated but BEFORE
    uploading to YouTube. Human must review and approve before publication.

    Args:
        ready: Editorial package that was approved by quality reviewer
        scene_paths: List of generated scene video file paths
        voiceover_path: Path to generated voiceover audio file
        final_video_path: Path to final assembled video
        thumbnail_path: Path to generated thumbnail image
        publish_datetime_iso: Proposed publish datetime in ISO format

    Returns:
        video_internal_id: Unique identifier for this draft (UUID4 string)

    Example:
        >>> video_id = save_draft_package(
        ...     ready=package,
        ...     scene_paths=["scene1.mp4", "scene2.mp4"],
        ...     voiceover_path="voice.wav",
        ...     final_video_path="final.mp4",
        ...     thumbnail_path="thumb.png",
        ...     publish_datetime_iso="2025-10-25T18:00:00Z"
        ... )
        >>> print(f"Draft saved: {video_id}")
        Draft saved: 123e4567-e89b-12d3-a456-426614174000
    """
    logger.info("Saving draft package to datastore (HUMAN_REVIEW_PENDING)...")

    # Generate unique internal ID
    video_internal_id = str(uuid.uuid4())

    datastore_path = _get_datastore_path()

    record = {
        "video_internal_id": video_internal_id,
        "production_state": "HUMAN_REVIEW_PENDING",
        "saved_at": datetime.now().isoformat(),
        "youtube_video_id": None,  # Not uploaded yet
        "status": ready.status,  # APPROVED from quality reviewer
        "title": ready.publishing.final_title,
        "proposed_publish_at": publish_datetime_iso,
        "actual_publish_at": None,  # Will be set after upload
        "video_plan": ready.video_plan.model_dump(),
        "script": ready.script.model_dump(),
        "visuals": ready.visuals.model_dump(),
        "publishing": ready.publishing.model_dump(),
        "files": {
            "scene_paths": scene_paths,
            "voiceover_path": voiceover_path,
            "final_video_path": final_video_path,
            "thumbnail_path": thumbnail_path
        },
        "llm_raw_script": llm_raw_script,  # Step 07: LLM original output for audit
        "final_script": final_script  # Step 07: Final validated script text
    }

    # Append to JSONL file
    with open(datastore_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"✓ Draft package saved to {datastore_path}")
    logger.info(f"  Internal ID: {video_internal_id}")
    logger.info(f"  Title: '{ready.publishing.final_title}'")
    logger.info(f"  State: HUMAN_REVIEW_PENDING")
    logger.info(f"  Final video: {final_video_path}")
    logger.info(f"  Thumbnail: {thumbnail_path}")

    return video_internal_id


def get_draft_package(video_internal_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a draft package by its internal ID.

    Args:
        video_internal_id: UUID string from save_draft_package()

    Returns:
        Full record dict if found, None otherwise

    Example:
        >>> draft = get_draft_package("123e4567-e89b-12d3-a456-426614174000")
        >>> if draft:
        ...     print(f"State: {draft['production_state']}")
        State: HUMAN_REVIEW_PENDING
    """
    logger.info(f"Retrieving draft package: {video_internal_id}...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.warning("Datastore file does not exist yet")
        return None

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())
            if record.get("video_internal_id") == video_internal_id:
                logger.info(f"✓ Found draft package")
                logger.info(f"  State: {record.get('production_state')}")
                logger.info(f"  Title: '{record.get('title')}'")
                return record

    logger.warning(f"Draft package not found: {video_internal_id}")
    return None


def mark_as_scheduled(
    video_internal_id: str,
    upload_result: UploadResult,
    approved_by: str,
    approved_at_iso: str
) -> None:
    """
    Marks a draft package as scheduled on YouTube with audit trail.

    Updates the record to production_state="SCHEDULED_ON_YOUTUBE" and
    adds YouTube video ID, actual publish time, and approval audit trail.

    This function should ONLY be called after successful YouTube upload
    and explicit human approval.

    Args:
        video_internal_id: UUID from save_draft_package()
        upload_result: Result from YouTube upload service
        approved_by: Identifier of approver (e.g., "dan@company", "alice")
        approved_at_iso: ISO 8601 timestamp of approval (UTC)

    Raises:
        ValueError: If draft not found or not in HUMAN_REVIEW_PENDING state

    Example:
        >>> upload_result = UploadResult(
        ...     youtube_video_id="abc123",
        ...     published_at="2025-10-25T18:00:00Z",
        ...     title="Test Video",
        ...     upload_timestamp="2025-10-24T12:00:00Z"
        ... )
        >>> mark_as_scheduled(
        ...     "123e4567-...",
        ...     upload_result,
        ...     approved_by="dan@company",
        ...     approved_at_iso="2025-10-24T20:11:52Z"
        ... )
    """
    logger.info(f"Marking package as scheduled: {video_internal_id}...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        raise ValueError(f"Datastore does not exist: {datastore_path}")

    # Read all records
    records = []
    found = False

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())

            # Update the matching record
            if record.get("video_internal_id") == video_internal_id:
                found = True

                # Validate state
                if record.get("production_state") != "HUMAN_REVIEW_PENDING":
                    current_state = record.get("production_state")
                    raise ValueError(
                        f"Cannot mark as scheduled: video is in state '{current_state}', "
                        f"expected 'HUMAN_REVIEW_PENDING'"
                    )

                # Update record
                record["production_state"] = "SCHEDULED_ON_YOUTUBE"
                record["youtube_video_id"] = upload_result.youtube_video_id
                record["actual_publish_at"] = upload_result.published_at
                record["upload_timestamp"] = upload_result.upload_timestamp
                record["upload_result"] = upload_result.model_dump()
                # Audit trail
                record["approved_by"] = approved_by
                record["approved_at_iso"] = approved_at_iso

                logger.info(f"✓ Record updated")
                logger.info(f"  Video ID: {upload_result.youtube_video_id}")
                logger.info(f"  Publish at: {upload_result.published_at}")
                logger.info(f"  Approved by: {approved_by} at {approved_at_iso}")

            records.append(record)

    if not found:
        raise ValueError(f"Draft package not found: {video_internal_id}")

    # Rewrite entire file with updated records
    with open(datastore_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"✓ Datastore updated: {datastore_path}")
    logger.info(f"  State: SCHEDULED_ON_YOUTUBE")


def list_scheduled_videos() -> List[Dict[str, Any]]:
    """
    Returns list of all videos that have been scheduled on YouTube.

    Only includes videos with production_state="SCHEDULED_ON_YOUTUBE"
    and a valid youtube_video_id.

    Returns:
        List of video records with metadata

    Example:
        >>> videos = list_scheduled_videos()
        >>> for video in videos:
        ...     print(f"{video['youtube_video_id']}: {video['title']}")
        abc123: Test Video
    """
    logger.info("Listing scheduled videos from datastore...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.warning("Datastore file does not exist yet")
        return []

    videos = []
    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())

            # Only include scheduled videos with YouTube ID
            if (record.get("production_state") == "SCHEDULED_ON_YOUTUBE" and
                record.get("youtube_video_id") and
                record["youtube_video_id"] not in [None, "PENDING_HUMAN_REVIEW"]):

                videos.append({
                    "video_internal_id": record.get("video_internal_id"),
                    "youtube_video_id": record["youtube_video_id"],
                    "title": record["title"],
                    "actual_publish_at": record.get("actual_publish_at"),
                    "saved_at": record["saved_at"],
                    "production_state": record["production_state"]
                })

    logger.info(f"✓ Found {len(videos)} scheduled videos")
    return videos


def list_pending_review() -> List[Dict[str, Any]]:
    """
    Returns list of all videos pending human review.

    Only includes videos with production_state="HUMAN_REVIEW_PENDING".
    These are videos that have been generated but not yet approved for
    publication to YouTube.

    Returns:
        List of video records with metadata needed for review

    Example:
        >>> pending = list_pending_review()
        >>> for video in pending:
        ...     print(f"{video['video_internal_id']}: {video['proposed_title']}")
        123e4567-...: AI Video Generation 2025
    """
    logger.info("Listing videos pending review from datastore...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.warning("Datastore file does not exist yet")
        return []

    videos = []
    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())

            # Only include pending review videos
            if record.get("production_state") == "HUMAN_REVIEW_PENDING":
                files = record.get("files", {})
                videos.append({
                    "video_internal_id": record.get("video_internal_id"),
                    "production_state": record["production_state"],
                    "final_video_path": files.get("final_video_path"),
                    "thumbnail_path": files.get("thumbnail_path"),
                    "proposed_title": record.get("title"),
                    "proposed_description": record.get("publishing", {}).get("description"),
                    "proposed_tags": record.get("publishing", {}).get("tags"),
                    "suggested_publishAt": record.get("proposed_publish_at"),
                    "saved_at": record.get("saved_at")
                })

    logger.info(f"✓ Found {len(videos)} videos pending review")
    return videos
