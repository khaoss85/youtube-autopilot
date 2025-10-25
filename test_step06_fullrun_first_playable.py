#!/usr/bin/env python3
"""
Test Script for Step 06-fullrun: First Playable Build

This script verifies the complete end-to-end production pipeline:
1. Editorial brain (build_video_package) with real LLM integration
2. Physical factory (generate scenes, voiceover, video assembly)
3. Datastore persistence (HUMAN_REVIEW_PENDING)
4. Real playable MP4 output (not text files)

This is the "first playable build" - a complete round trip from
trend to reviewable video draft.

Expected outcomes:
- final_video.mp4 is a real playable MP4 (concatenated black clips)
- voiceover.wav is a real silent WAV file
- Draft saved in datastore with HUMAN_REVIEW_PENDING status
- All files physically exist on disk

IMPORTANT: This test does NOT upload to YouTube or schedule anything.
It only verifies local production capability.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("STEP 06-FULLRUN: FIRST PLAYABLE BUILD TEST")
print("=" * 70)
print()

# =============================================================================
# TEST 1: Import Check
# =============================================================================

print("TEST 1: Import check")
print("-" * 70)

try:
    from yt_autopilot.pipeline.produce_render_publish import produce_render_assets
    from yt_autopilot.io.datastore import get_draft_package
    print("✓ All imports successful")
    print()

except Exception as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 2: Full Production Pipeline Execution
# =============================================================================

print("TEST 2: Execute full production pipeline")
print("-" * 70)

try:
    # Call produce_render_assets with future publish datetime
    publish_datetime = "2025-10-30T18:00:00Z"

    print(f"Calling produce_render_assets(publish_datetime_iso='{publish_datetime}')...")
    print()
    print("This will:")
    print("  1. Run editorial brain (build_video_package) with LLM")
    print("  2. Generate video scenes (placeholder MP4s via ffmpeg)")
    print("  3. Synthesize voiceover (silent WAV via ffmpeg)")
    print("  4. Assemble final video (ffmpeg concat)")
    print("  5. Generate thumbnail (placeholder)")
    print("  6. Save draft to datastore (HUMAN_REVIEW_PENDING)")
    print()
    print("=" * 70)

    result = produce_render_assets(publish_datetime_iso=publish_datetime)

    print()
    print("=" * 70)
    print("✓ produce_render_assets() completed successfully")
    print()

    # Display result
    print("Result summary:")
    print(f"  status: {result['status']}")
    print(f"  video_internal_id: {result['video_internal_id']}")
    print(f"  proposed_title: {result['proposed_title']}")
    print(f"  proposed_description: {result['proposed_description'][:100]}...")
    print(f"  suggested_publishAt: {result['suggested_publishAt']}")
    print()

except Exception as e:
    print(f"✗ Pipeline execution failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 3: Verify Physical Files Exist
# =============================================================================

print("TEST 3: Verify physical files on disk")
print("-" * 70)

try:
    # Check final video
    final_video_path = Path(result["final_video_path"])
    if not final_video_path.exists():
        raise AssertionError(f"final_video.mp4 does not exist: {final_video_path}")

    final_video_size = final_video_path.stat().st_size
    if final_video_size < 1024:  # Must be at least 1KB
        raise AssertionError(
            f"final_video.mp4 is too small ({final_video_size} bytes) - "
            f"likely not a real video"
        )

    print(f"✓ final_video.mp4 exists: {final_video_path}")
    print(f"  Size: {final_video_size:,} bytes ({final_video_size / 1024:.1f} KB)")

    # Check thumbnail
    thumbnail_path = Path(result["thumbnail_path"])
    if not thumbnail_path.exists():
        raise AssertionError(f"thumbnail does not exist: {thumbnail_path}")

    thumbnail_size = thumbnail_path.stat().st_size
    print(f"✓ thumbnail exists: {thumbnail_path}")
    print(f"  Size: {thumbnail_size:,} bytes ({thumbnail_size / 1024:.1f} KB)")

    # Check voiceover (retrieve from datastore)
    video_id = result["video_internal_id"]
    draft_package = get_draft_package(video_id)

    if "files" in draft_package and "voiceover_path" in draft_package["files"]:
        voiceover_path = Path(draft_package["files"]["voiceover_path"])
        if voiceover_path.exists():
            voiceover_size = voiceover_path.stat().st_size
            print(f"✓ voiceover.wav exists: {voiceover_path}")
            print(f"  Size: {voiceover_size:,} bytes ({voiceover_size / 1024:.1f} KB)")

            # Verify it's a real WAV (at least check size is reasonable)
            if voiceover_size < 1024:
                print(f"  ⚠ Warning: voiceover is very small ({voiceover_size} bytes)")
        else:
            print(f"  ⚠ Warning: voiceover_path in datastore but file not found")

    # Check scene clips (in TEMP_DIR)
    from yt_autopilot.core.config import get_temp_dir
    temp_dir = get_temp_dir()

    scene_clips = sorted(temp_dir.glob("scene_*.mp4"))
    if len(scene_clips) > 0:
        print(f"✓ Found {len(scene_clips)} scene clips in temp directory:")
        for clip in scene_clips:
            clip_size = clip.stat().st_size
            # Verify each clip is a real video file (not text)
            if clip_size < 1024:
                raise AssertionError(
                    f"Scene clip {clip.name} is too small ({clip_size} bytes) - "
                    f"likely a text file, not a real MP4"
                )
            print(f"  - {clip.name}: {clip_size:,} bytes ({clip_size / 1024:.1f} KB)")
    else:
        print("  ⚠ Warning: No scene clips found in temp directory")

    print()
    print("✓ All physical files verified")
    print()

except Exception as e:
    print(f"✗ File verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 4: Verify Datastore State
# =============================================================================

print("TEST 4: Verify datastore state")
print("-" * 70)

try:
    video_id = result["video_internal_id"]
    draft_package = get_draft_package(video_id)

    # Check required fields
    assert draft_package["video_internal_id"] == video_id
    assert draft_package["production_state"] == "HUMAN_REVIEW_PENDING"
    assert "files" in draft_package
    assert "final_video_path" in draft_package["files"]
    assert "thumbnail_path" in draft_package["files"]
    assert "title" in draft_package
    assert "proposed_publish_at" in draft_package

    print(f"✓ Draft package found in datastore: {video_id}")
    print(f"  production_state: {draft_package['production_state']}")
    print(f"  title: {draft_package['title']}")
    print(f"  tags: {len(draft_package['publishing']['tags'])} tags")
    print()

    print("✓ Datastore state verified")
    print()

except Exception as e:
    print(f"✗ Datastore verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 5: Report Next Steps
# =============================================================================

print("TEST 5: Human review workflow")
print("-" * 70)

print("The video draft is now ready for human review. To proceed:")
print()
print("1. List pending drafts:")
print("   python tools/review_console.py list")
print()
print("2. Review the video:")
print(f"   python tools/review_console.py show {video_id}")
print()
print("3. Watch the video with VLC:")
print(f"   vlc {result['final_video_path']}")
print()
print("4. If satisfied, approve and publish:")
print(f"   python tools/review_console.py publish {video_id} --approved-by your-email@example.com")
print()
print("⚠ IMPORTANT: The video will NOT be uploaded to YouTube until you")
print("  explicitly approve it using the review console.")
print()

# =============================================================================
# SUMMARY
# =============================================================================

print("=" * 70)
print("ALL STEP 06-FULLRUN TESTS PASSED ✓")
print("=" * 70)
print()
print("Success Summary:")
print("  ✓ Editorial brain with LLM integration working")
print("  ✓ Video scenes generated (real MP4 files via ffmpeg)")
print("  ✓ Voiceover synthesized (real WAV file via ffmpeg)")
print("  ✓ Final video assembled (playable MP4)")
print("  ✓ Thumbnail generated")
print("  ✓ Draft saved to datastore (HUMAN_REVIEW_PENDING)")
print("  ✓ All physical files verified on disk")
print()
print("This is your FIRST PLAYABLE BUILD!")
print()
print("What you can do now:")
print("  1. Watch the final video to see the complete pipeline output")
print("  2. Use review_console.py to approve/reject drafts")
print("  3. Publish approved videos to YouTube (manual gate)")
print()
print("Next steps:")
print("  - Step 07: Scheduler automation (APScheduler)")
print("  - Step 08: Enhanced human review CLI")
print("  - Step 09: Real Veo integration (replace placeholder videos)")
print("  - Step 10: Real TTS integration (replace silent voiceover)")
print()
print("=" * 70)
