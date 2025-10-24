"""
Full Production Pipeline: Editorial Brain + Physical Factory with Human Gate

This module orchestrates the complete video production workflow with
a mandatory human approval step before publication.

Production Workflow:
1. produce_render_assets() - Generate all physical assets (video, thumbnail)
   → State: HUMAN_REVIEW_PENDING
   → NO automatic upload

2. Human reviews video and approves/rejects

3. publish_after_approval() - Upload to YouTube only after human approval
   → State: SCHEDULED_ON_YOUTUBE

This ensures ZERO risk of publishing inappropriate content automatically.
The system generates content, but humans gate publication.
"""

from datetime import datetime
from typing import Dict, Any
from yt_autopilot.core.logger import logger
from yt_autopilot.core.schemas import ReadyForFactory, UploadResult, PublishingPackage

# Import from pipeline (editorial brain)
from yt_autopilot.pipeline.build_video_package import build_video_package

# Import from services (factory)
from yt_autopilot.services.video_gen_service import generate_scenes
from yt_autopilot.services.tts_service import synthesize_voiceover
from yt_autopilot.services.video_assemble_service import assemble_final_video
from yt_autopilot.services.thumbnail_service import generate_thumbnail
from yt_autopilot.services.youtube_uploader import upload_and_schedule

# Import from io (persistence)
from yt_autopilot.io.datastore import (
    save_draft_package,
    get_draft_package,
    mark_as_scheduled
)


def produce_render_assets(publish_datetime_iso: str) -> Dict[str, Any]:
    """
    Phase 1: Generate all physical assets and save as draft pending human review.

    Workflow:
    1. Run editorial brain (build_video_package)
    2. If REJECTED by quality reviewer: abort and return error
    3. If APPROVED: generate physical assets
       a. Generate video scenes (Veo API)
       b. Generate voiceover (TTS)
       c. Assemble final video (ffmpeg)
       d. Generate thumbnail image
    4. Save to datastore with state "HUMAN_REVIEW_PENDING"
    5. Return package info for human review

    ⚠️ This function does NOT upload to YouTube.
    ⚠️ Human must explicitly approve before calling publish_after_approval().

    Args:
        publish_datetime_iso: Proposed publish datetime in ISO format
                              (e.g., "2025-10-25T18:00:00Z")

    Returns:
        Dict with keys:
        - status: "READY_FOR_REVIEW" or "REJECTED"
        - video_internal_id: UUID for draft (if READY_FOR_REVIEW)
        - final_video_path: Path to final .mp4 (if READY_FOR_REVIEW)
        - thumbnail_path: Path to thumbnail image (if READY_FOR_REVIEW)
        - proposed_title: Editorial title (if READY_FOR_REVIEW)
        - proposed_description: SEO description (if READY_FOR_REVIEW)
        - proposed_tags: SEO tags (if READY_FOR_REVIEW)
        - suggested_publishAt: Proposed publish time (if READY_FOR_REVIEW)
        - reason: Rejection reason (if REJECTED)

    Raises:
        RuntimeError: If asset generation fails (Veo, TTS, ffmpeg errors)

    Example:
        >>> result = produce_render_assets("2025-10-25T18:00:00Z")
        >>> if result["status"] == "READY_FOR_REVIEW":
        ...     print(f"Video ready: {result['final_video_path']}")
        ...     print(f"Review and approve, then call:")
        ...     print(f"publish_after_approval('{result['video_internal_id']}')")
        ... else:
        ...     print(f"Rejected: {result['reason']}")
    """
    logger.info("=" * 70)
    logger.info("PRODUCTION PIPELINE: Phase 1 - Generate Assets")
    logger.info("=" * 70)

    # STEP 1: Editorial Brain - Generate approved content package
    logger.info("STEP 1/5: Running editorial brain...")
    ready = build_video_package()

    if ready.status == "REJECTED":
        logger.error(f"✗ Editorial brain rejected package")
        logger.error(f"  Reason: {ready.rejection_reason}")
        logger.info("=" * 70)
        logger.info("PRODUCTION ABORTED: Package rejected by quality reviewer")
        logger.info("=" * 70)
        return {
            "status": "REJECTED",
            "reason": ready.rejection_reason
        }

    logger.info(f"✓ Editorial brain approved package")
    logger.info(f"  Title: '{ready.publishing.final_title}'")
    logger.info(f"  Scenes: {len(ready.visuals.scenes)}")
    total_duration = sum(scene.est_duration_seconds for scene in ready.visuals.scenes)
    logger.info(f"  Duration: ~{total_duration}s")

    # STEP 2: Generate video scenes using Veo API
    logger.info("")
    logger.info("STEP 2/5: Generating video scenes...")
    logger.info(f"  Requesting {len(ready.visuals.scenes)} scenes from Veo API")

    try:
        scene_paths = generate_scenes(ready.visuals, max_retries=2)
        logger.info(f"✓ All scenes generated: {len(scene_paths)} files")
    except Exception as e:
        logger.error(f"✗ Scene generation failed: {e}")
        raise RuntimeError(f"Veo API scene generation failed: {e}")

    # STEP 3: Generate voiceover using TTS
    logger.info("")
    logger.info("STEP 3/5: Generating voiceover...")
    logger.info(f"  Text length: {len(ready.script.full_voiceover_text)} chars")

    try:
        voiceover_path = synthesize_voiceover(ready.script)
        logger.info(f"✓ Voiceover generated: {voiceover_path}")
    except Exception as e:
        logger.error(f"✗ Voiceover generation failed: {e}")
        raise RuntimeError(f"TTS voiceover generation failed: {e}")

    # STEP 4: Assemble final video with ffmpeg
    logger.info("")
    logger.info("STEP 4/5: Assembling final video...")

    try:
        final_video_path = assemble_final_video(
            scene_paths=scene_paths,
            voiceover_path=voiceover_path,
            visuals=ready.visuals
        )
        logger.info(f"✓ Final video assembled: {final_video_path}")
    except Exception as e:
        logger.error(f"✗ Video assembly failed: {e}")
        raise RuntimeError(f"ffmpeg video assembly failed: {e}")

    # STEP 5: Generate thumbnail
    logger.info("")
    logger.info("STEP 5/5: Generating thumbnail...")

    try:
        thumbnail_path = generate_thumbnail(ready.publishing)
        logger.info(f"✓ Thumbnail generated: {thumbnail_path}")
    except Exception as e:
        logger.error(f"✗ Thumbnail generation failed: {e}")
        raise RuntimeError(f"Thumbnail generation failed: {e}")

    # Save to datastore as draft (HUMAN_REVIEW_PENDING)
    logger.info("")
    logger.info("Saving draft package to datastore...")
    video_internal_id = save_draft_package(
        ready=ready,
        scene_paths=scene_paths,
        voiceover_path=voiceover_path,
        final_video_path=final_video_path,
        thumbnail_path=thumbnail_path,
        publish_datetime_iso=publish_datetime_iso
    )

    logger.info("")
    logger.info("=" * 70)
    logger.info("PHASE 1 COMPLETE: Assets ready for human review")
    logger.info("=" * 70)
    logger.info(f"📹 Video: {final_video_path}")
    logger.info(f"🖼️  Thumbnail: {thumbnail_path}")
    logger.info(f"📊 Title: '{ready.publishing.final_title}'")
    logger.info(f"⏱️  Duration: ~{total_duration}s")
    logger.info(f"🆔 Internal ID: {video_internal_id}")
    logger.info("")
    logger.info("⚠️  STATUS: HUMAN_REVIEW_PENDING")
    logger.info("")
    logger.info("Next step: Review video, then call:")
    logger.info(f"  publish_after_approval('{video_internal_id}')")
    logger.info("=" * 70)

    return {
        "status": "READY_FOR_REVIEW",
        "video_internal_id": video_internal_id,
        "final_video_path": final_video_path,
        "thumbnail_path": thumbnail_path,
        "proposed_title": ready.publishing.final_title,
        "proposed_description": ready.publishing.description,
        "proposed_tags": ready.publishing.tags,
        "suggested_publishAt": publish_datetime_iso
    }


def publish_after_approval(video_internal_id: str, approved_by: str) -> Dict[str, Any]:
    """
    Phase 2: Publish approved video package to YouTube with audit trail.

    This function should ONLY be called after human review and approval.
    It uploads the video to YouTube with scheduled publication and records
    who approved the publication and when.

    ⚠️ BRAND SAFETY: This is the ONLY point where content is uploaded to YouTube.
    ⚠️ This function must NEVER be called automatically by a scheduler.

    Args:
        video_internal_id: UUID from produce_render_assets()
        approved_by: Identifier of approver (e.g., "dan@company", "alice")

    Returns:
        Dict with keys:
        - status: "SCHEDULED" or "ERROR"
        - video_id: YouTube video ID (if SCHEDULED)
        - publishAt: Actual publish datetime (if SCHEDULED)
        - title: Video title (if SCHEDULED)
        - approved_by: Approver identifier (if SCHEDULED)
        - approved_at_iso: Approval timestamp (if SCHEDULED)
        - reason: Error message (if ERROR)

    Raises:
        RuntimeError: If upload fails
        ValueError: If draft not found or not in correct state

    Example:
        >>> # After human reviews and approves
        >>> result = publish_after_approval(
        ...     "123e4567-e89b-12d3-a456-426614174000",
        ...     approved_by="dan@company"
        ... )
        >>> if result["status"] == "SCHEDULED":
        ...     print(f"Scheduled: {result['video_id']}")
        ...     print(f"Approved by: {result['approved_by']}")
    """
    logger.info("=" * 70)
    logger.info("PUBLISH PIPELINE: Phase 2 - Upload to YouTube")
    logger.info("=" * 70)
    logger.info(f"Internal ID: {video_internal_id}")

    # Retrieve draft package from datastore
    logger.info("Retrieving draft package from datastore...")
    draft = get_draft_package(video_internal_id)

    if draft is None:
        logger.error(f"✗ Draft package not found: {video_internal_id}")
        return {
            "status": "ERROR",
            "reason": f"Draft package not found: {video_internal_id}"
        }

    # Validate state
    if draft.get("production_state") != "HUMAN_REVIEW_PENDING":
        current_state = draft.get("production_state")
        logger.error(f"✗ Invalid state: {current_state}")
        logger.error(f"  Expected: HUMAN_REVIEW_PENDING")
        return {
            "status": "ERROR",
            "reason": f"Video not in HUMAN_REVIEW_PENDING state (current: {current_state})"
        }

    # Extract data from draft
    final_video_path = draft["files"]["final_video_path"]
    thumbnail_path = draft["files"]["thumbnail_path"]
    publish_at_iso = draft["proposed_publish_at"]

    # Reconstruct PublishingPackage from saved data
    publishing_data = draft["publishing"]
    publishing = PublishingPackage(**publishing_data)

    logger.info(f"✓ Draft package retrieved")
    logger.info(f"  Title: '{draft['title']}'")
    logger.info(f"  Video: {final_video_path}")
    logger.info(f"  Thumbnail: {thumbnail_path}")
    logger.info(f"  Scheduled publish: {publish_at_iso}")

    # Upload to YouTube
    logger.info("")
    logger.info("Uploading to YouTube...")
    logger.info(f"  Approved by: {approved_by}")

    try:
        upload_result = upload_and_schedule(
            video_path=final_video_path,
            publishing=publishing,
            publish_datetime_iso=publish_at_iso,
            thumbnail_path=thumbnail_path
        )
        logger.info(f"✓ Upload successful")
        logger.info(f"  Video ID: {upload_result.youtube_video_id}")
        logger.info(f"  Will be published at: {upload_result.published_at}")
    except Exception as e:
        logger.error(f"✗ Upload failed: {e}")
        raise RuntimeError(f"YouTube upload failed: {e}")

    # Generate approval timestamp
    approved_at_iso = datetime.utcnow().isoformat() + "Z"

    # Update datastore: HUMAN_REVIEW_PENDING → SCHEDULED_ON_YOUTUBE
    logger.info("")
    logger.info("Updating datastore with audit trail...")
    mark_as_scheduled(video_internal_id, upload_result, approved_by, approved_at_iso)

    logger.info("")
    logger.info("=" * 70)
    logger.info("PHASE 2 COMPLETE: Video scheduled on YouTube")
    logger.info("=" * 70)
    logger.info(f"✅ STATUS: SCHEDULED_ON_YOUTUBE")
    logger.info(f"YouTube Video ID: {upload_result.youtube_video_id}")
    logger.info(f"Publish at: {upload_result.published_at}")
    logger.info(f"Title: {upload_result.title}")
    logger.info(f"Approved by: {approved_by} at {approved_at_iso}")
    logger.info("=" * 70)

    return {
        "status": "SCHEDULED",
        "video_id": upload_result.youtube_video_id,
        "publishAt": upload_result.published_at,
        "title": upload_result.title,
        "approved_by": approved_by,
        "approved_at_iso": approved_at_iso
    }
