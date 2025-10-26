"""
Full Production Pipeline: Editorial Brain + Physical Factory with 2-Gate Workflow

This module orchestrates the complete video production workflow with
TWO mandatory human approval gates to minimize wasted API costs.

Step 07.3 Production Workflow (2-Gate):

GATE 1 - Script Review (Cheap):
1. generate_script_draft() - Generate script only (editorial brain)
   → State: SCRIPT_PENDING_REVIEW
   → Cost: ~$0.01 LLM call
   → Human reviews script concept

2. Human approves script → triggers asset generation

GATE 2 - Video Review (After expensive generation):
3. produce_render_assets() - Generate physical assets (Sora/TTS/DALL-E)
   → State: VIDEO_PENDING_REVIEW
   → Cost: $$$  (video + audio + thumbnail)
   → Human reviews final video

4. Human approves video

FINAL - Publication:
5. publish_after_approval() - Upload to YouTube
   → State: SCHEDULED_ON_YOUTUBE

This ensures:
- ZERO risk of publishing inappropriate content automatically
- 70-80% reduction in wasted API costs (reject bad scripts before generation)
- Humans gate BOTH script quality AND final video quality
"""

from datetime import datetime
from typing import Dict, Any
from yt_autopilot.core.logger import logger
from yt_autopilot.core.schemas import ReadyForFactory, UploadResult, PublishingPackage
from yt_autopilot.core import asset_manager  # Step 07.4: Asset organization

# Import from pipeline (editorial brain)
from yt_autopilot.pipeline.build_video_package import build_video_package

# Import from services (factory)
from yt_autopilot.services.video_gen_service import generate_scenes
from yt_autopilot.services.tts_service import synthesize_voiceover
from yt_autopilot.services.video_assemble_service import assemble_final_video
from yt_autopilot.services.thumbnail_service import generate_thumbnail
from yt_autopilot.services.youtube_uploader import upload_and_schedule
from yt_autopilot.services import provider_tracker

# Import from io (persistence)
from yt_autopilot.io.datastore import (
    save_draft_package,
    get_draft_package,
    mark_as_scheduled,
    save_script_draft,  # Step 07.3: Gate 1 (script review)
    get_script_draft,   # Step 07.3: Retrieve approved script
    _asset_paths_to_dict  # Step 07.4: AssetPaths serialization
)


def generate_script_draft(publish_datetime_iso: str, workspace_id: str) -> Dict[str, Any]:
    """
    Step 07.3 - GATE 1: Generate script draft and save for human review.

    This is the FIRST gate in the 2-gate workflow. It generates only the
    editorial content (script, visual plan, publishing metadata) without
    creating any expensive physical assets.

    Cost: ~$0.01 (LLM call only)
    Benefit: Human can reject bad scripts BEFORE wasting $$$ on video generation

    Workflow:
    1. Run editorial brain (build_video_package)
    2. If REJECTED by quality reviewer: return error
    3. If APPROVED: save script draft with state SCRIPT_PENDING_REVIEW
    4. Return script_internal_id for human review

    Args:
        publish_datetime_iso: Proposed publish datetime (e.g., "2025-11-01T18:00:00Z")
        workspace_id: Workspace identifier for filtering and organization

    Returns:
        Dict with keys:
        - status: "SCRIPT_READY_FOR_REVIEW" or "REJECTED"
        - script_internal_id: UUID for script draft (if READY)
        - proposed_title: Editorial title (if READY)
        - script_preview: First 200 chars of voiceover (if READY)
        - scene_count: Number of scenes planned (if READY)
        - estimated_duration: Total video duration in seconds (if READY)
        - reason: Rejection reason (if REJECTED)

    Example:
        >>> result = generate_script_draft("2025-11-01T18:00:00Z", "tech_ai_creator")
        >>> if result["status"] == "SCRIPT_READY_FOR_REVIEW":
        ...     print(f"Script ID: {result['script_internal_id']}")
        ...     print("Review via: run.py review show-script <ID>")
        ...     print("Approve via: run.py review approve-script <ID>")
    """
    logger.info("=" * 70)
    logger.info("SCRIPT GENERATION: Gate 1 - Generate Script Draft")
    logger.info("=" * 70)
    logger.info(f"Workspace: {workspace_id}")

    # STEP 1: Editorial Brain - Generate approved content package
    logger.info("STEP 1: Running editorial brain...")
    ready = build_video_package(workspace_id=workspace_id)

    if ready.status == "REJECTED":
        logger.error(f"✗ Editorial brain rejected package")
        logger.error(f"  Reason: {ready.rejection_reason}")
        logger.info("=" * 70)
        logger.info("SCRIPT GENERATION ABORTED: Package rejected by quality reviewer")
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

    # STEP 2: Save script draft (NO asset generation yet)
    logger.info("")
    logger.info("STEP 2: Saving script draft for human review...")
    script_internal_id = save_script_draft(ready, publish_datetime_iso, workspace_id)

    logger.info("")
    logger.info("=" * 70)
    logger.info("GATE 1 COMPLETE: Script ready for human review")
    logger.info("=" * 70)
    logger.info(f"📝 Script ID: {script_internal_id}")
    logger.info(f"📊 Title: '{ready.publishing.final_title}'")
    logger.info(f"🎬 Scenes: {len(ready.visuals.scenes)}")
    logger.info(f"⏱️  Duration: ~{total_duration}s")
    logger.info("")
    logger.info("⚠️  STATUS: SCRIPT_PENDING_REVIEW")
    logger.info("")
    logger.info("Next steps:")
    logger.info(f"  1. Review script: review_console.py show-script {script_internal_id}")
    logger.info(f"  2. Approve script: review_console.py approve-script {script_internal_id} --approved-by \"your@email\"")
    logger.info(f"  3. Assets will be generated ONLY after approval (saves $$$)")
    logger.info("=" * 70)

    return {
        "status": "SCRIPT_READY_FOR_REVIEW",
        "script_internal_id": script_internal_id,
        "proposed_title": ready.publishing.final_title,
        "script_preview": ready.script.full_voiceover_text[:200],
        "scene_count": len(ready.visuals.scenes),
        "estimated_duration": total_duration
    }


def produce_render_assets(script_internal_id: str) -> Dict[str, Any]:
    """
    Step 07.3 - GATE 2: Generate physical assets from approved script.

    This is the SECOND gate in the 2-gate workflow. It retrieves an approved
    script from Gate 1 and generates expensive physical assets (video, audio, thumbnail).

    Cost: $$$ (Sora video + TTS audio + DALL-E thumbnail)
    Prerequisite: Script must be in READY_FOR_GENERATION state (approved by human)

    Workflow:
    1. Retrieve approved script draft from datastore
    2. Verify script is in READY_FOR_GENERATION state
    3. Generate physical assets:
       a. Generate video scenes (Sora/Veo API)
       b. Generate voiceover (TTS)
       c. Assemble final video (ffmpeg)
       d. Generate thumbnail image (DALL-E)
    4. Save to datastore with state VIDEO_PENDING_REVIEW
    5. Return package info for human review

    ⚠️ This function does NOT upload to YouTube.
    ⚠️ Human must explicitly approve VIDEO before calling publish_after_approval().

    Args:
        script_internal_id: UUID of approved script from generate_script_draft()

    Returns:
        Dict with keys:
        - status: "VIDEO_READY_FOR_REVIEW" or "ERROR"
        - video_internal_id: UUID for video draft (if READY)
        - final_video_path: Path to final .mp4 (if READY)
        - thumbnail_path: Path to thumbnail image (if READY)
        - proposed_title: Editorial title (if READY)
        - proposed_description: SEO description (if READY)
        - proposed_tags: SEO tags (if READY)
        - suggested_publishAt: Proposed publish time (if READY)
        - reason: Error message (if ERROR)

    Raises:
        RuntimeError: If asset generation fails (Sora, TTS, ffmpeg errors)
        ValueError: If script not found or not in READY_FOR_GENERATION state

    Example:
        >>> # After script approval via review_console.py
        >>> result = produce_render_assets("script-uuid-from-gate-1")
        >>> if result["status"] == "VIDEO_READY_FOR_REVIEW":
        ...     print(f"Video ready: {result['final_video_path']}")
        ...     print("Review via: review_console.py show-video <ID>")
    """
    logger.info("=" * 70)
    logger.info("ASSET GENERATION: Gate 2 - Generate Physical Assets")
    logger.info("=" * 70)
    logger.info(f"Script ID: {script_internal_id}")

    # Step 07.2: Reset provider tracking for this generation
    provider_tracker.reset_tracking()

    # STEP 1: Retrieve approved script from datastore
    logger.info("STEP 1/5: Retrieving approved script...")
    script_draft = get_script_draft(script_internal_id)

    if script_draft is None:
        logger.error(f"✗ Script draft not found: {script_internal_id}")
        logger.info("=" * 70)
        logger.info("ASSET GENERATION ABORTED: Script not found")
        logger.info("=" * 70)
        return {
            "status": "ERROR",
            "reason": f"Script draft not found: {script_internal_id}"
        }

    # Verify script is in READY_FOR_GENERATION state
    current_state = script_draft.get("production_state")
    if current_state != "READY_FOR_GENERATION":
        logger.error(f"✗ Invalid state: {current_state}")
        logger.error(f"  Expected: READY_FOR_GENERATION")
        logger.error(f"  Script must be approved via review_console.py first")
        logger.info("=" * 70)
        logger.info("ASSET GENERATION ABORTED: Script not approved")
        logger.info("=" * 70)
        return {
            "status": "ERROR",
            "reason": f"Script not approved (state: {current_state})"
        }

    logger.info(f"✓ Script draft retrieved and approved")
    logger.info(f"  Title: '{script_draft.get('title')}'")
    logger.info(f"  Workspace: {script_draft.get('workspace_id')}")
    logger.info(f"  Approved by: {script_draft.get('script_approved_by')}")
    logger.info(f"  Approved at: {script_draft.get('script_approved_at')}")

    # Extract workspace_id for save_draft_package
    workspace_id = script_draft.get("workspace_id")
    if not workspace_id:
        logger.warning("⚠ No workspace_id in script draft (legacy record) - using 'unknown'")
        workspace_id = "unknown"

    # Reconstruct ReadyForFactory from saved script draft
    from yt_autopilot.core.schemas import VideoPlan, VideoScript, VisualPlan, PublishingPackage, VisualScene

    ready = ReadyForFactory(
        status=script_draft["status"],
        video_plan=VideoPlan(**script_draft["video_plan"]),
        script=VideoScript(**script_draft["script"]),
        visuals=VisualPlan(**script_draft["visuals"]),
        publishing=PublishingPackage(**script_draft["publishing"]),
        llm_raw_script=script_draft.get("llm_raw_script"),
        final_script_text=script_draft.get("final_script")
    )

    publish_datetime_iso = script_draft["proposed_publish_at"]
    total_duration = sum(scene["est_duration_seconds"] for scene in script_draft["visuals"]["scenes"])
    logger.info(f"  Scenes: {len(ready.visuals.scenes)}")
    logger.info(f"  Duration: ~{total_duration}s")

    # Step 07.4: Create unique asset directory structure for this video
    logger.info("")
    logger.info("Creating asset directory structure...")
    asset_paths = asset_manager.create_asset_paths(video_id=script_internal_id)
    logger.info(f"  Output directory: {asset_paths.output_dir}")

    # STEP 2: Generate video scenes using Sora/Veo API
    logger.info("")
    logger.info("STEP 2/5: Generating video scenes...")
    logger.info(f"  Requesting {len(ready.visuals.scenes)} scenes from Veo API")

    try:
        scene_paths = generate_scenes(ready.visuals, asset_paths, max_retries=2)
        logger.info(f"✓ All scenes generated: {len(scene_paths)} files")
    except Exception as e:
        logger.error(f"✗ Scene generation failed: {e}")
        raise RuntimeError(f"Veo API scene generation failed: {e}")

    # STEP 3: Generate voiceover using TTS
    logger.info("")
    logger.info("STEP 3/5: Generating voiceover...")
    logger.info(f"  Text length: {len(ready.script.full_voiceover_text)} chars")

    try:
        voiceover_path = synthesize_voiceover(ready.script, asset_paths)
        logger.info(f"✓ Voiceover generated: {voiceover_path}")
    except Exception as e:
        logger.error(f"✗ Voiceover generation failed: {e}")
        raise RuntimeError(f"TTS voiceover generation failed: {e}")

    # STEP 4: Assemble final video with ffmpeg
    logger.info("")
    logger.info("STEP 4/5: Assembling final video...")

    try:
        # Step 07.4: Pass asset_paths for organized output
        final_video_path = assemble_final_video(
            scene_paths=scene_paths,
            voiceover_path=voiceover_path,
            visuals=ready.visuals,
            asset_paths=asset_paths
        )
        logger.info(f"✓ Final video assembled: {final_video_path}")
    except Exception as e:
        logger.error(f"✗ Video assembly failed: {e}")
        raise RuntimeError(f"ffmpeg video assembly failed: {e}")

    # STEP 5: Generate thumbnail
    logger.info("")
    logger.info("STEP 5/5: Generating thumbnail...")

    try:
        thumbnail_path = generate_thumbnail(ready.publishing, asset_paths)
        logger.info(f"✓ Thumbnail generated: {thumbnail_path}")
    except Exception as e:
        logger.error(f"✗ Thumbnail generation failed: {e}")
        raise RuntimeError(f"Thumbnail generation failed: {e}")

    # Save to datastore as draft (VIDEO_PENDING_REVIEW)
    logger.info("")
    logger.info("Saving draft package to datastore...")

    # Step 07.2: Collect provider tracking information
    providers = provider_tracker.get_all_providers()

    # Step 07.4: Use paths from asset_paths (already populated by services)
    video_internal_id = save_draft_package(
        ready=ready,
        scene_paths=asset_paths.scene_video_paths,  # Step 07.4: From asset tracking
        voiceover_path=str(asset_paths.voiceover_path),
        final_video_path=str(asset_paths.final_video_path),
        thumbnail_path=str(asset_paths.thumbnail_path),
        publish_datetime_iso=publish_datetime_iso,
        workspace_id=workspace_id,  # Step 08: Multi-workspace support
        llm_raw_script=ready.llm_raw_script,  # Step 07: Audit trail
        final_script=ready.final_script_text,  # Step 07: Audit trail
        thumbnail_prompt=ready.publishing.thumbnail_concept,  # Step 07.2: Creative quality
        video_provider_used=providers["video_provider"],  # Step 07.2: Provider tracking
        voice_provider_used=providers["voice_provider"],  # Step 07.2: Provider tracking
        thumb_provider_used=providers["thumb_provider"],   # Step 07.2: Provider tracking
        script_internal_id=script_internal_id  # Step 07.3: Link to approved script
    )

    logger.info("")
    logger.info("=" * 70)
    logger.info("GATE 2 COMPLETE: Video ready for human review")
    logger.info("=" * 70)
    logger.info(f"📹 Video: {final_video_path}")
    logger.info(f"🖼️  Thumbnail: {thumbnail_path}")
    logger.info(f"📊 Title: '{ready.publishing.final_title}'")
    logger.info(f"⏱️  Duration: ~{total_duration}s")
    logger.info(f"🆔 Video ID: {video_internal_id}")
    logger.info(f"🔗 Script ID: {script_internal_id}")
    logger.info("")
    logger.info("⚠️  STATUS: VIDEO_PENDING_REVIEW")
    logger.info("")
    logger.info("Next steps:")
    logger.info(f"  1. Review video: review_console.py show-video {video_internal_id}")
    logger.info(f"  2. Publish video: review_console.py publish {video_internal_id} --approved-by \"your@email\"")
    logger.info("=" * 70)

    return {
        "status": "VIDEO_READY_FOR_REVIEW",
        "video_internal_id": video_internal_id,
        "script_internal_id": script_internal_id,
        "output_dir": asset_paths.output_dir,  # Step 07.4: Asset directory location
        "final_video_path": final_video_path,
        "thumbnail_path": thumbnail_path,
        "voiceover_path": voiceover_path,  # Step 07.4: Voiceover location
        "scene_paths": scene_paths,  # Step 07.4: Individual scene locations
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
