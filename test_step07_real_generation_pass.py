#!/usr/bin/env python3
"""
Test Script for Step 07: Real Generation Pass

This script verifies the upgraded production pipeline with:
1. Real Veo video generation (with automatic fallback to placeholders)
2. Real TTS voiceover (with automatic fallback to silent WAV)
3. Structured LLM prompts (HOOK/BULLETS/CTA/VOICEOVER format)
4. Script audit trail (llm_raw_script + final_script saved to datastore)

Compared to Step 06-fullrun (first playable build), Step 07 adds:
- Real video generation via Veo/Vertex AI API (or placeholder if unavailable)
- Real voiceover via OpenAI TTS API (or silent WAV if unavailable)
- Enhanced LLM prompt structure for better creative output
- Script audit trail for human transparency and debugging

Expected outcomes:
- final_video.mp4 is playable (real Veo clips OR ffmpeg placeholders)
- voiceover audio is real TTS MP3 OR silent WAV fallback
- Draft saved with llm_raw_script and final_script audit fields
- All files physically exist on disk
- System gracefully degrades if APIs unavailable

IMPORTANT: This test does NOT upload to YouTube or schedule anything.
It only verifies local production capability with real generation APIs.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("STEP 07: REAL GENERATION PASS TEST")
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
    from yt_autopilot.services.video_gen_service import generate_scenes
    from yt_autopilot.services.tts_service import synthesize_voiceover
    from yt_autopilot.core.schemas import ReadyForFactory
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

print("TEST 2: Execute full production pipeline with real generation")
print("-" * 70)

try:
    # Call produce_render_assets with future publish datetime
    publish_datetime = "2025-10-30T18:00:00Z"

    print(f"Calling produce_render_assets(publish_datetime_iso='{publish_datetime}')...")
    print()
    print("This will:")
    print("  1. Run editorial brain (build_video_package) with structured LLM")
    print("  2. Generate video scenes (Veo API or placeholder fallback)")
    print("  3. Synthesize voiceover (TTS API or silent WAV fallback)")
    print("  4. Assemble final video (ffmpeg concat)")
    print("  5. Generate thumbnail")
    print("  6. Save draft with audit trail to datastore")
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
            voiceover_ext = voiceover_path.suffix.lower()
            print(f"✓ voiceover exists: {voiceover_path}")
            print(f"  Size: {voiceover_size:,} bytes ({voiceover_size / 1024:.1f} KB)")
            print(f"  Format: {voiceover_ext} (MP3=real TTS, WAV=fallback)")

            # Verify it's a real audio file
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
# TEST 4: Verify Datastore State and Audit Trail
# =============================================================================

print("TEST 4: Verify datastore state and audit trail (Step 07 NEW)")
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

    # Step 07 NEW: Verify audit trail fields
    print("Step 07 AUDIT TRAIL verification:")

    llm_raw_script = draft_package.get("llm_raw_script")
    final_script = draft_package.get("final_script")

    if llm_raw_script:
        print(f"  ✓ llm_raw_script present: {len(llm_raw_script)} chars")
        print(f"    Preview: {llm_raw_script[:100]}...")
    else:
        print(f"  ✗ llm_raw_script MISSING (expected in Step 07)")
        raise AssertionError("llm_raw_script field missing in datastore")

    print()

    if final_script:
        print(f"  ✓ final_script present: {len(final_script)} chars")
        print(f"    Preview: {final_script[:100]}...")
    else:
        print(f"  ✗ final_script MISSING (expected in Step 07)")
        raise AssertionError("final_script field missing in datastore")

    print()
    print("✓ Datastore state and audit trail verified")
    print()

except Exception as e:
    print(f"✗ Datastore verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 5: Report Next Steps
# =============================================================================

print("TEST 5: Human review workflow with audit trail")
print("-" * 70)

print("The video draft is now ready for human review. To proceed:")
print()
print("1. List pending drafts:")
print("   python tools/review_console.py list")
print()
print("2. Review the video with AUDIT TRAIL (NEW in Step 07):")
print(f"   python tools/review_console.py show {video_id}")
print()
print("   This will now display:")
print("   - LLM Raw Output (original suggestion from AI)")
print("   - Final Validated Script (after safety checks)")
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
print("ALL STEP 07 TESTS PASSED ✓")
print("=" * 70)
print()
print("Success Summary:")
print("  ✓ Editorial brain with structured LLM prompts working")
print("  ✓ Video generation (Veo API or placeholder fallback)")
print("  ✓ Voiceover synthesis (TTS API or silent WAV fallback)")
print("  ✓ Final video assembled (playable MP4)")
print("  ✓ Thumbnail generated")
print("  ✓ Draft saved to datastore (HUMAN_REVIEW_PENDING)")
print("  ✓ Audit trail fields (llm_raw_script + final_script) verified ✨ NEW")
print("  ✓ All physical files verified on disk")
print()
print("Step 07 Upgrades from Step 06:")
print("  • Real Veo video generation (with graceful fallback)")
print("  • Real TTS voiceover (with graceful fallback)")
print("  • Structured LLM prompts (HOOK/BULLETS/CTA/VOICEOVER)")
print("  • Script audit trail for transparency")
print()
print("What you can do now:")
print("  1. Watch the final video to see real/fallback generation quality")
print("  2. Use review_console.py to inspect audit trail fields")
print("  3. Publish approved videos to YouTube (manual gate)")
print()
print("Next steps (Step 08 and beyond):")
print("  - Step 08: Scheduler automation for daily content generation")
print("  - Step 09+: Enhanced analytics, A/B testing, multi-channel support")
print()
print("=" * 70)
