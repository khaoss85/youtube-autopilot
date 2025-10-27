"""
Datastore Module: Local persistence for video packages and metrics.

This module handles storage of video packages, upload results, and analytics
in a local JSONL database for historical tracking and analysis.

Production States (Step 07.3: 2-Gate Workflow):
- SCRIPT_PENDING_REVIEW: Script generated, awaiting human approval to proceed
- READY_FOR_GENERATION: Script approved, ready to generate video assets
- VIDEO_PENDING_REVIEW: Video assets generated, awaiting human approval to publish
- SCHEDULED_ON_YOUTUBE: Video uploaded and scheduled on YouTube

Legacy States (backward compatibility):
- HUMAN_REVIEW_PENDING: Equivalent to VIDEO_PENDING_REVIEW (pre-Step 07.3)
"""

import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from yt_autopilot.core.schemas import ReadyForFactory, UploadResult, VideoMetrics, AssetPaths
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


def _asset_paths_to_dict(asset_paths: AssetPaths) -> Dict[str, Any]:
    """
    Converts AssetPaths object to dict for datastore storage (Step 07.4).

    Args:
        asset_paths: AssetPaths object with file locations

    Returns:
        Dict suitable for datastore 'files' field
    """
    return {
        "video_id": asset_paths.video_id,
        "output_dir": asset_paths.output_dir,
        "scene_paths": asset_paths.scene_video_paths,
        "voiceover_path": asset_paths.voiceover_path or "",
        "final_video_path": asset_paths.final_video_path or "",
        "thumbnail_path": asset_paths.thumbnail_path or "",
        "metadata_path": asset_paths.metadata_path or ""
    }


def _dict_to_asset_paths(files_dict: Dict[str, Any]) -> Optional[AssetPaths]:
    """
    Converts datastore 'files' dict to AssetPaths object (Step 07.4).

    Args:
        files_dict: Dict from datastore 'files' field

    Returns:
        AssetPaths object, or None if files_dict is empty/invalid
    """
    if not files_dict or "video_id" not in files_dict:
        return None

    return AssetPaths(
        video_id=files_dict.get("video_id", ""),
        output_dir=files_dict.get("output_dir", ""),
        final_video_path=files_dict.get("final_video_path"),
        thumbnail_path=files_dict.get("thumbnail_path"),
        voiceover_path=files_dict.get("voiceover_path"),
        scene_video_paths=files_dict.get("scene_paths", []),
        metadata_path=files_dict.get("metadata_path")
    )


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


def get_videos_performance_summary(
    titles: List[str],
    workspace_id: Optional[str] = None
) -> Dict[str, int]:
    """
    Retrieves performance summary (views) for a list of video titles.

    This function enables learning loops by connecting video titles to their
    actual performance metrics. Used to inform AI selection with what worked.

    Graceful fallback behavior:
    - Video not in datastore → skip (not produced yet)
    - Video not published (youtube_video_id = None) → skip (no metrics possible)
    - Video published but no metrics → skip (metrics not collected yet)
    - Metrics exist → return latest views count

    Args:
        titles: List of video titles (typically from workspace recent_titles)
        workspace_id: Optional workspace filter for multi-channel setups

    Returns:
        Dict mapping title → views for videos with available metrics.
        Dict may be empty if no metrics available (graceful fallback).

    Example:
        >>> titles = ["5 errori gambe", "Proteine: quante?", "Stretching mattutino"]
        >>> perf = get_videos_performance_summary(titles, "gym_fitness_pro")
        >>> print(perf)
        {'5 errori gambe': 12500, 'Proteine: quante?': 3200}
        # "Stretching mattutino" not in result (no metrics yet)
    """
    logger.info(f"Retrieving performance summary for {len(titles)} titles...")

    config = get_config()
    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.info("Datastore does not exist yet (no videos produced)")
        return {}

    # Build title → youtube_video_id mapping from datastore
    title_to_video_id = {}

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())

            # Filter by workspace if specified
            if workspace_id and record.get("workspace_id") != workspace_id:
                continue

            title = record.get("title")
            youtube_id = record.get("youtube_video_id")

            # Only consider published videos (with real YouTube ID)
            if title in titles and youtube_id:
                title_to_video_id[title] = youtube_id

    logger.info(f"  Found {len(title_to_video_id)} published videos")

    # Retrieve metrics for each video
    performance_summary = {}

    for title, youtube_id in title_to_video_id.items():
        metrics_history = get_metrics_history(youtube_id)

        if metrics_history:
            # Use latest metrics (most recent snapshot)
            latest_metrics = metrics_history[-1]
            performance_summary[title] = latest_metrics.views
            logger.debug(f"  '{title[:50]}': {latest_metrics.views:,} views")

    logger.info(f"✓ Performance summary built: {len(performance_summary)} videos with metrics")
    return performance_summary


def save_draft_package(
    ready: ReadyForFactory,
    scene_paths: List[str],
    voiceover_path: str,
    final_video_path: str,
    thumbnail_path: str,
    publish_datetime_iso: str,
    workspace_id: str,
    llm_raw_script: Optional[str] = None,
    final_script: Optional[str] = None,
    thumbnail_prompt: Optional[str] = None,
    video_provider_used: Optional[str] = None,
    voice_provider_used: Optional[str] = None,
    thumb_provider_used: Optional[str] = None,
    script_internal_id: Optional[str] = None,
    visual_context_id: Optional[str] = None,
    visual_context_name: Optional[str] = None
) -> str:
    """
    Saves a draft video package pending human review (Step 07.3: Gate 2).

    Creates a record with production_state="VIDEO_PENDING_REVIEW" and
    generates a unique video_internal_id for future reference.

    Step 07.3 2-Gate Workflow:
    - This is Gate 2: Video assets are generated and ready for review
    - Optionally linked to script_internal_id from Gate 1 approval

    This function is called AFTER physical assets are generated but BEFORE
    uploading to YouTube. Human must review video and approve before publication.

    Args:
        ready: Editorial package that was approved by quality reviewer
        scene_paths: List of generated scene video file paths
        voiceover_path: Path to generated voiceover audio file
        final_video_path: Path to final assembled video
        thumbnail_path: Path to generated thumbnail image
        publish_datetime_iso: Proposed publish datetime in ISO format
        workspace_id: Workspace identifier for filtering and organization
        llm_raw_script: (Optional) Raw LLM output before validation
        final_script: (Optional) Final validated script text
        thumbnail_prompt: (Optional) Step 07.2: Prompt used for thumbnail generation
        video_provider_used: (Optional) Step 07.2: Video provider (OPENAI_VIDEO/VEO/FALLBACK_PLACEHOLDER)
        voice_provider_used: (Optional) Step 07.2: Voice provider (REAL_TTS/FALLBACK_SILENT)
        thumb_provider_used: (Optional) Step 07.2: Thumbnail provider (OPENAI_IMAGE/FALLBACK_PLACEHOLDER)
        script_internal_id: (Optional) Step 07.3: Link to approved script from Gate 1
        visual_context_id: (Optional) Step 09: Visual context ID used (e.g., 'home_gym')
        visual_context_name: (Optional) Step 09: Visual context name used (e.g., 'Home Gym Setting')

    Returns:
        video_internal_id: Unique identifier for this draft (UUID4 string)

    Example:
        >>> # Step 07.3: After script approval
        >>> video_id = save_draft_package(
        ...     ready=package,
        ...     scene_paths=["scene1.mp4", "scene2.mp4"],
        ...     voiceover_path="voice.wav",
        ...     final_video_path="final.mp4",
        ...     thumbnail_path="thumb.png",
        ...     publish_datetime_iso="2025-10-25T18:00:00Z",
        ...     workspace_id="tech_ai_creator",
        ...     script_internal_id="script-uuid-from-gate-1"
        ... )
        >>> print(f"Video draft saved: {video_id}")
        Video draft saved: 123e4567-e89b-12d3-a456-426614174000
    """
    logger.info("Saving draft package to datastore (VIDEO_PENDING_REVIEW)...")

    # Generate unique internal ID
    video_internal_id = str(uuid.uuid4())

    datastore_path = _get_datastore_path()

    record = {
        "video_internal_id": video_internal_id,
        "workspace_id": workspace_id,  # Step 08: Multi-workspace support
        "script_internal_id": script_internal_id,  # Step 07.3: Link to script from Gate 1
        "production_state": "VIDEO_PENDING_REVIEW",  # Step 07.3: Updated state name
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
        "final_script": final_script,  # Step 07: Final validated script text
        # Step 07.2: Creative quality tracking
        "thumbnail_prompt": thumbnail_prompt,
        "video_provider_used": video_provider_used,
        "voice_provider_used": voice_provider_used,
        "thumb_provider_used": thumb_provider_used,
        # Step 09: Visual context tracking for retention analytics
        "visual_context_id": visual_context_id,
        "visual_context_name": visual_context_name
    }

    # Append to JSONL file
    with open(datastore_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"✓ Draft package saved to {datastore_path}")
    logger.info(f"  Internal ID: {video_internal_id}")
    logger.info(f"  Workspace: {workspace_id}")
    logger.info(f"  Title: '{ready.publishing.final_title}'")
    logger.info(f"  State: VIDEO_PENDING_REVIEW")  # Step 07.3: Updated state
    if script_internal_id:
        logger.info(f"  Linked script: {script_internal_id}")  # Step 07.3: Track link
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

    Step 07.3: Supports both VIDEO_PENDING_REVIEW and HUMAN_REVIEW_PENDING.

    This function should ONLY be called after successful YouTube upload
    and explicit human approval.

    Args:
        video_internal_id: UUID from save_draft_package()
        upload_result: Result from YouTube upload service
        approved_by: Identifier of approver (e.g., "dan@company", "alice")
        approved_at_iso: ISO 8601 timestamp of approval (UTC)

    Raises:
        ValueError: If draft not found or not in correct state for publishing

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

                # Validate state (Step 07.3: Support both new and legacy states)
                current_state = record.get("production_state")
                valid_states = ["VIDEO_PENDING_REVIEW", "HUMAN_REVIEW_PENDING"]
                if current_state not in valid_states:
                    raise ValueError(
                        f"Cannot mark as scheduled: video is in state '{current_state}', "
                        f"expected one of {valid_states}"
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


def list_pending_review(workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns list of videos pending human review (Step 07.3: Gate 2).

    Step 07.3: Supports both VIDEO_PENDING_REVIEW and legacy HUMAN_REVIEW_PENDING.
    These are videos that have been generated but not yet approved for
    publication to YouTube.

    Args:
        workspace_id: Optional workspace filter. If None, returns all workspaces.

    Returns:
        List of video records with metadata needed for review

    Example:
        >>> pending = list_pending_review(workspace_id="tech_ai_creator")
        >>> for video in pending:
        ...     print(f"{video['video_internal_id']}: {video['proposed_title']}")
        123e4567-...: AI Video Generation 2025
    """
    if workspace_id:
        logger.info(f"Listing videos pending review for workspace: {workspace_id}")
    else:
        logger.info("Listing videos pending review from all workspaces...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.warning("Datastore file does not exist yet")
        return []

    videos = []
    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line.strip())

            # Step 07.3: Include both new and legacy states for backward compatibility
            state = record.get("production_state")
            if state not in ["VIDEO_PENDING_REVIEW", "HUMAN_REVIEW_PENDING"]:
                continue

            # Filter by workspace if specified
            if workspace_id and record.get("workspace_id") != workspace_id:
                continue

            files = record.get("files", {})
            videos.append({
                "video_internal_id": record.get("video_internal_id"),
                "workspace_id": record.get("workspace_id"),
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


# ==============================================================================
# Step 07.3: Script Review Workflow Functions (2-Gate)
# ==============================================================================

def save_script_draft(
    ready: ReadyForFactory,
    publish_datetime_iso: str,
    workspace_id: str
) -> str:
    """
    Saves script draft package pending human review (Step 07.3: Gate 1).

    Creates a record with production_state="SCRIPT_PENDING_REVIEW" containing
    only the editorial package (script, plan, visuals, publishing metadata).
    NO physical assets are generated yet.

    This is the FIRST gate in the 2-gate workflow. After human approval,
    the script will transition to READY_FOR_GENERATION and trigger asset creation.

    Args:
        ready: Editorial package from build_video_package()
        publish_datetime_iso: Proposed publish datetime (e.g., "2025-11-01T18:00:00Z")
        workspace_id: Workspace identifier for filtering and organization

    Returns:
        script_internal_id: UUID for this script draft

    Example:
        >>> ready = build_video_package(workspace_id="tech_ai_creator")
        >>> script_id = save_script_draft(ready, "2025-11-01T18:00:00Z", "tech_ai_creator")
        >>> # Human reviews script via review_console.py
        >>> # If approved: approve_script_for_generation(script_id, "dan@company")
    """
    logger.info("Saving script draft to datastore (SCRIPT_PENDING_REVIEW)...")

    datastore_path = _get_datastore_path()
    script_internal_id = str(uuid.uuid4())

    # Step 09: Extract visual context tracking from visuals for top-level access
    visual_context_id = ready.visuals.visual_context_id if hasattr(ready.visuals, 'visual_context_id') else None
    visual_context_name = ready.visuals.visual_context_name if hasattr(ready.visuals, 'visual_context_name') else None

    # Step 09.5: Extract character profile tracking from visuals for top-level access
    character_profile_id = ready.visuals.character_profile_id if hasattr(ready.visuals, 'character_profile_id') else None
    character_description = ready.visuals.character_description if hasattr(ready.visuals, 'character_description') else None

    record = {
        "script_internal_id": script_internal_id,
        "workspace_id": workspace_id,  # Step 08: Multi-workspace support
        "production_state": "SCRIPT_PENDING_REVIEW",
        "saved_at": datetime.now().isoformat(),
        "status": ready.status,  # APPROVED from quality reviewer
        "title": ready.publishing.final_title,
        "proposed_publish_at": publish_datetime_iso,

        # Editorial content (for review)
        "video_plan": ready.video_plan.model_dump(),
        "script": ready.script.model_dump(),
        "visuals": ready.visuals.model_dump(),
        "publishing": ready.publishing.model_dump(),

        # Audit trail (Step 07)
        "llm_raw_script": ready.llm_raw_script,
        "final_script": ready.final_script_text,

        # Step 09: Visual context tracking (top-level for analytics)
        "visual_context_id": visual_context_id,
        "visual_context_name": visual_context_name,

        # Step 09.5: Character consistency tracking (top-level for analytics)
        "character_profile_id": character_profile_id,
        "character_description": character_description,

        # Placeholders (will be filled after Gate 2)
        "video_internal_id": None,  # Assigned when assets generated
        "youtube_video_id": None,
        "files": {},
        "video_provider_used": None,
        "voice_provider_used": None,
        "thumb_provider_used": None,
        "thumbnail_prompt": ready.publishing.thumbnail_concept
    }

    # Append to JSONL
    with open(datastore_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"✓ Script draft saved to {datastore_path}")
    logger.info(f"  Script ID: {script_internal_id}")
    logger.info(f"  Workspace: {workspace_id}")
    logger.info(f"  Title: '{ready.publishing.final_title}'")
    logger.info(f"  State: SCRIPT_PENDING_REVIEW")
    logger.info(f"  Next: Human review via run.py review scripts")

    return script_internal_id


def list_pending_script_review(workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns list of scripts pending human review (Step 07.3: Gate 1).

    Only includes scripts with production_state="SCRIPT_PENDING_REVIEW".
    These are scripts that have passed QualityReviewer but not yet approved
    by human to proceed with expensive asset generation.

    Args:
        workspace_id: Optional workspace filter. If None, returns all workspaces.

    Returns:
        List of script draft dicts with metadata for review

    Example:
        >>> scripts = list_pending_script_review(workspace_id="tech_ai_creator")
        >>> for script in scripts:
        ...     print(f"{script['script_internal_id']}: {script['proposed_title']}")
    """
    if workspace_id:
        logger.info(f"Listing scripts pending review for workspace: {workspace_id}")
    else:
        logger.info("Listing scripts pending review from all workspaces...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.warning(f"Datastore file not found: {datastore_path}")
        return []

    scripts = []

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line.strip())

            # Filter by state
            if record.get("production_state") != "SCRIPT_PENDING_REVIEW":
                continue

            # Filter by workspace if specified
            if workspace_id and record.get("workspace_id") != workspace_id:
                continue

            scripts.append({
                "script_internal_id": record.get("script_internal_id"),
                "workspace_id": record.get("workspace_id"),
                "production_state": record["production_state"],
                "proposed_title": record.get("title"),
                "proposed_description": record.get("publishing", {}).get("description"),
                "script": record.get("script"),  # Full script for display
                "visuals": record.get("visuals"),  # Visual plan for display
                "video_plan": record.get("video_plan"),  # Video plan for display
                "suggested_publishAt": record.get("proposed_publish_at"),
                "saved_at": record.get("saved_at")
            })

    logger.info(f"✓ Found {len(scripts)} scripts pending review")
    return scripts


def get_script_draft(script_internal_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a specific script draft by ID (Step 07.3).

    Args:
        script_internal_id: UUID of the script draft

    Returns:
        Script draft record dict, or None if not found

    Example:
        >>> draft = get_script_draft("123e4567-e89b-12d3-a456-426614174000")
        >>> if draft:
        ...     print(f"Script: {draft['script']}")
    """
    logger.info(f"Retrieving script draft: {script_internal_id}...")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.warning(f"Datastore file not found: {datastore_path}")
        return None

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line.strip())
            if record.get("script_internal_id") == script_internal_id:
                logger.info(f"✓ Found script draft")
                logger.info(f"  State: {record.get('production_state')}")
                logger.info(f"  Title: '{record.get('title')}'")
                return record

    logger.warning(f"Script draft not found: {script_internal_id}")
    return None


def approve_script_for_generation(
    script_internal_id: str,
    approved_by: str
) -> None:
    """
    Approves script and marks ready for asset generation (Step 07.3: Gate 1 → Gate 2).

    Changes production_state from SCRIPT_PENDING_REVIEW to READY_FOR_GENERATION.
    Records who approved and when for audit trail.

    After this approval, the script is ready for produce_render_assets() to
    generate expensive video/audio/thumbnail assets.

    Args:
        script_internal_id: UUID of the script draft
        approved_by: Identifier of approver (e.g., "dan@company")

    Raises:
        ValueError: If script not found or not in correct state

    Example:
        >>> approve_script_for_generation(
        ...     "123e4567-e89b-12d3-a456-426614174000",
        ...     approved_by="dan@company"
        ... )
        >>> # Now ready for: produce_render_assets(script_id)
    """
    logger.info(f"Approving script for generation: {script_internal_id}")
    logger.info(f"  Approved by: {approved_by}")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        raise ValueError(f"Datastore file not found: {datastore_path}")

    # Read all records
    with open(datastore_path, "r", encoding="utf-8") as f:
        records = [json.loads(line.strip()) for line in f if line.strip()]

    # Find and update the target record
    found = False
    for record in records:
        if record.get("script_internal_id") == script_internal_id:
            found = True

            # Validate state
            current_state = record.get("production_state")
            if current_state != "SCRIPT_PENDING_REVIEW":
                raise ValueError(
                    f"Cannot approve script: state is '{current_state}', "
                    f"expected 'SCRIPT_PENDING_REVIEW'"
                )

            # Update state
            record["production_state"] = "READY_FOR_GENERATION"
            record["script_approved_by"] = approved_by
            record["script_approved_at"] = datetime.now().isoformat()

            logger.info(f"✓ Script approved and marked READY_FOR_GENERATION")
            break

    if not found:
        raise ValueError(f"Script draft not found: {script_internal_id}")

    # Write back to file (atomic)
    with open(datastore_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"✓ Datastore updated: {datastore_path}")


def _fuzzy_match(text1: str, text2: str, threshold: float = 0.7) -> bool:
    """
    Check if two texts have significant word overlap.

    Uses simple word-based matching to detect similar topics.

    Args:
        text1: First text to compare
        text2: Second text to compare
        threshold: Minimum overlap ratio (default 0.7 = 70%)

    Returns:
        True if overlap ratio > threshold

    Example:
        >>> _fuzzy_match("AI tools productivity", "Productivity with AI tools", 0.7)
        True
        >>> _fuzzy_match("Python tutorial", "JavaScript guide", 0.7)
        False
    """
    if not text1 or not text2:
        return False

    # Normalize and tokenize
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return False

    # Calculate overlap ratio (Jaccard similarity)
    overlap = len(words1 & words2)
    union = len(words1 | words2)

    if union == 0:
        return False

    similarity = overlap / union
    return similarity > threshold


def is_topic_already_produced(working_title: str, workspace_id: Optional[str] = None) -> bool:
    """
    Checks if a topic (working_title) has already been produced or scheduled.

    Checks against all records in datastore across all production states:
    - SCRIPT_PENDING_REVIEW: Script waiting for human review
    - READY_FOR_GENERATION: Script approved, generating video assets
    - VIDEO_PENDING_REVIEW: Video generated, waiting for human review
    - SCHEDULED_ON_YOUTUBE: Video uploaded and scheduled

    Uses fuzzy matching (70% word overlap) to detect similar topics even
    if phrasing is slightly different.

    Step 08 Phase 3: Duplicate prevention for trend selection

    Args:
        working_title: Original trend keyword from TrendCandidate
        workspace_id: Optional workspace filter (check only within workspace)

    Returns:
        True if topic already exists in datastore

    Example:
        >>> is_topic_already_produced("AI productivity tools")
        False  # New topic
        >>> is_topic_already_produced("Productivity with AI tools")
        True   # Already produced (fuzzy match)
    """
    logger.debug(f"Checking if topic already produced: '{working_title}'")

    datastore_path = _get_datastore_path()

    if not datastore_path.exists():
        logger.debug("Datastore file does not exist yet - no duplicates")
        return False

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line.strip())

            # Filter by workspace if specified
            if workspace_id:
                video_plan = record.get("video_plan", {})
                record_workspace = video_plan.get("workspace_id")
                if record_workspace and record_workspace != workspace_id:
                    continue

            # Check both working_title (from video_plan) and final title
            video_plan = record.get("video_plan", {})
            existing_working = video_plan.get("working_title", "")
            existing_final = record.get("title", "")

            # Fuzzy match against both
            if _fuzzy_match(working_title, existing_working, threshold=0.7):
                logger.debug(
                    f"  Duplicate found (working_title): '{existing_working}' "
                    f"(state: {record.get('production_state', 'N/A')})"
                )
                return True

            if _fuzzy_match(working_title, existing_final, threshold=0.7):
                logger.debug(
                    f"  Duplicate found (final_title): '{existing_final}' "
                    f"(state: {record.get('production_state', 'N/A')})"
                )
                return True

    logger.debug("  No duplicates found")
    return False
