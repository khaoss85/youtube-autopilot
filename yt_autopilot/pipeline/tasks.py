"""
Reusable Tasks for Production Workflow

This module provides atomic task functions that can be scheduled by
the automation scheduler (Step 06).

Tasks:
1. task_generate_assets_for_review() - Generate video assets (automated)
2. task_publish_after_human_ok() - Upload to YouTube (manual trigger only)
3. task_collect_metrics() - Collect analytics for all scheduled videos (automated)

⚠️ IMPORTANT:
- task_generate_assets_for_review() CAN be automated (creates drafts for review)
- task_publish_after_human_ok() MUST NEVER be automated (requires human approval)
- task_collect_metrics() CAN be automated (just reads data)
"""

from typing import Dict, Any
from yt_autopilot.core.logger import logger
from yt_autopilot.pipeline.produce_render_publish import (
    produce_render_assets,
    publish_after_approval
)
from yt_autopilot.services.youtube_analytics import fetch_video_metrics
from yt_autopilot.io.datastore import list_scheduled_videos, save_metrics


def task_generate_assets_for_review(publish_datetime_iso: str) -> Dict[str, Any]:
    """
    Task 1: Generate video assets and save as draft for human review.

    This task CAN be automated by a scheduler because it does NOT publish
    anything publicly. It only generates assets and saves them with state
    "HUMAN_REVIEW_PENDING".

    Workflow:
    1. Run editorial brain to generate content package
    2. Generate video scenes, voiceover, thumbnail
    3. Assemble final video
    4. Save to datastore with HUMAN_REVIEW_PENDING state
    5. Human reviews and approves/rejects manually

    Args:
        publish_datetime_iso: Proposed publish datetime (e.g., "2025-10-25T18:00:00Z")

    Returns:
        Dict from produce_render_assets() with status and draft info

    Example (scheduler usage):
        >>> # Scheduler runs daily at 10:00 AM
        >>> from datetime import datetime, timedelta
        >>> publish_time = (datetime.now() + timedelta(hours=24)).isoformat() + "Z"
        >>> result = task_generate_assets_for_review(publish_time)
        >>> if result["status"] == "READY_FOR_REVIEW":
        ...     # Send notification to human reviewer
        ...     notify_human(f"Video ready for review: {result['video_internal_id']}")
    """
    logger.info("=" * 70)
    logger.info("TASK: Generate assets for review")
    logger.info("=" * 70)
    logger.info(f"Proposed publish time: {publish_datetime_iso}")

    result = produce_render_assets(publish_datetime_iso)

    if result["status"] == "READY_FOR_REVIEW":
        logger.info("✓ Task complete: Assets generated, awaiting human review")
        logger.info(f"  Internal ID: {result['video_internal_id']}")
        logger.info(f"  Video: {result['final_video_path']}")
    else:
        logger.warning(f"✗ Task complete: Package rejected")
        logger.warning(f"  Reason: {result.get('reason')}")

    logger.info("=" * 70)

    return result


def task_publish_after_human_ok(video_internal_id: str) -> Dict[str, Any]:
    """
    Task 2: Publish approved video to YouTube (MANUAL TRIGGER ONLY).

    ⚠️ CRITICAL: This task MUST NEVER be called automatically by a scheduler.
    ⚠️ It must ONLY be called manually after explicit human approval.

    This is the final brand safety gate. Humans must review the video content,
    thumbnail, title, and description before publication.

    Args:
        video_internal_id: UUID from task_generate_assets_for_review()

    Returns:
        Dict from publish_after_approval() with YouTube video ID and status

    Example (manual usage):
        >>> # Human reviews video and approves
        >>> video_id = "123e4567-e89b-12d3-a456-426614174000"
        >>> result = task_publish_after_human_ok(video_id)
        >>> if result["status"] == "SCHEDULED":
        ...     print(f"Published: {result['video_id']}")
    """
    logger.info("=" * 70)
    logger.info("TASK: Publish after human approval")
    logger.info("=" * 70)
    logger.info(f"Internal ID: {video_internal_id}")
    logger.info("⚠️  This task requires manual human approval")

    result = publish_after_approval(video_internal_id)

    if result["status"] == "SCHEDULED":
        logger.info("✓ Task complete: Video scheduled on YouTube")
        logger.info(f"  YouTube ID: {result['video_id']}")
        logger.info(f"  Publish at: {result['publishAt']}")
    else:
        logger.error(f"✗ Task failed: {result.get('reason')}")

    logger.info("=" * 70)

    return result


def task_collect_metrics() -> None:
    """
    Task 3: Collect analytics metrics for all scheduled videos.

    This task CAN be automated by a scheduler because it only reads data
    and does not publish anything.

    Workflow:
    1. Get list of all videos with state SCHEDULED_ON_YOUTUBE
    2. For each video:
       a. Fetch metrics from YouTube Analytics API
       b. Save metrics to datastore for historical tracking

    This maintains up-to-date KPIs for all published videos.

    Raises:
        RuntimeError: If metrics fetch fails for any video

    Example (scheduler usage):
        >>> # Scheduler runs daily at midnight
        >>> task_collect_metrics()
        # Fetches metrics for all scheduled videos
    """
    logger.info("=" * 70)
    logger.info("TASK: Collect video metrics")
    logger.info("=" * 70)

    # Get all videos that have been scheduled on YouTube
    logger.info("Fetching list of scheduled videos...")
    videos = list_scheduled_videos()

    if not videos:
        logger.warning("No scheduled videos found - nothing to collect")
        logger.info("=" * 70)
        return

    logger.info(f"✓ Found {len(videos)} scheduled videos")
    logger.info("")

    # Collect metrics for each video
    success_count = 0
    error_count = 0

    for i, video in enumerate(videos, 1):
        video_id = video["youtube_video_id"]
        title = video["title"]

        logger.info(f"[{i}/{len(videos)}] Collecting metrics for: {video_id}")
        logger.info(f"  Title: '{title}'")

        try:
            # Fetch metrics from YouTube Analytics
            metrics = fetch_video_metrics(video_id)

            # Save to datastore
            save_metrics(video_id, metrics)

            logger.info(f"  ✓ Metrics saved")
            logger.info(f"    Views: {metrics.views:,}")
            logger.info(f"    CTR: {metrics.ctr:.2%}")
            logger.info("")

            success_count += 1

        except Exception as e:
            logger.error(f"  ✗ Failed to collect metrics: {e}")
            logger.error("")
            error_count += 1

    # Summary
    logger.info("=" * 70)
    logger.info("TASK COMPLETE: Metrics collection")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Errors: {error_count}")
    logger.info(f"  Total: {len(videos)}")
    logger.info("=" * 70)

    if error_count > 0:
        raise RuntimeError(f"Metrics collection failed for {error_count} videos")
