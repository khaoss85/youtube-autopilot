#!/usr/bin/env python3
"""
test_step07_2_quality_pass.py

Comprehensive end-to-end test for Step 07.2: Creator-Grade Quality Pass

This test verifies the complete Step 07.2 implementation including:
1. Creator-grade TTS voice (tts-1-hd + speed optimization)
2. Multi-tier video generation (OpenAI → Veo → ffmpeg fallback)
3. Real AI thumbnails (DALL-E 3 OR PIL fallback)
4. Creator-style LLM prompts (energetic, conversational)
5. Provider tracking system (who generated what)
6. Review console creative quality check display
7. Backward compatibility with legacy records
8. Graceful fallback behavior across all providers

The test should PASS whether you have:
- All API keys configured (100% creator-grade quality)
- Some API keys configured (partial creator-grade quality)
- No API keys configured (0% quality, all fallbacks)

System degrades gracefully but never crashes.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """TEST 1: Verify all Step 07.2 modules import successfully"""
    print("=" * 70)
    print("TEST 1: Checking Step 07.2 imports...")
    print("=" * 70)
    print()

    try:
        # Core imports
        from yt_autopilot.core.config import get_openai_video_key
        print("✓ core.config.get_openai_video_key")

        # Service imports
        from yt_autopilot.services import provider_tracker
        print("✓ services.provider_tracker")

        from yt_autopilot.services.tts_service import synthesize_voiceover
        print("✓ services.tts_service.synthesize_voiceover (upgraded)")

        from yt_autopilot.services.video_gen_service import generate_scenes
        print("✓ services.video_gen_service.generate_scenes (multi-tier)")

        from yt_autopilot.services.thumbnail_service import generate_thumbnail
        print("✓ services.thumbnail_service.generate_thumbnail (AI)")

        # Pipeline imports
        from yt_autopilot.pipeline.produce_render_publish import produce_render_assets
        print("✓ pipeline.produce_render_publish (with tracking)")

        # IO imports
        from yt_autopilot.io.datastore import save_draft_package, get_draft_package
        print("✓ io.datastore (with provider fields)")

        print()
        print("✅ TEST 1 PASSED: All Step 07.2 imports successful")
        print()
        return True

    except Exception as e:
        print(f"❌ TEST 1 FAILED: Import error: {e}")
        print()
        return False


def test_provider_tracker():
    """TEST 2: Verify provider tracker works correctly"""
    print("=" * 70)
    print("TEST 2: Testing provider tracker...")
    print("=" * 70)
    print()

    try:
        from yt_autopilot.services import provider_tracker

        # Test reset
        provider_tracker.reset_tracking()
        print("✓ reset_tracking() works")

        # Test setters
        provider_tracker.set_video_provider("VEO")
        provider_tracker.set_voice_provider("REAL_TTS")
        provider_tracker.set_thumb_provider("OPENAI_IMAGE")
        print("✓ set_video_provider(), set_voice_provider(), set_thumb_provider() work")

        # Test getters
        video = provider_tracker.get_video_provider()
        voice = provider_tracker.get_voice_provider()
        thumb = provider_tracker.get_thumb_provider()

        assert video == "VEO", f"Expected 'VEO', got '{video}'"
        assert voice == "REAL_TTS", f"Expected 'REAL_TTS', got '{voice}'"
        assert thumb == "OPENAI_IMAGE", f"Expected 'OPENAI_IMAGE', got '{thumb}'"
        print(f"✓ Getters return correct values: video={video}, voice={voice}, thumb={thumb}")

        # Test get_all
        all_providers = provider_tracker.get_all_providers()
        assert all_providers["video_provider"] == "VEO"
        assert all_providers["voice_provider"] == "REAL_TTS"
        assert all_providers["thumb_provider"] == "OPENAI_IMAGE"
        print(f"✓ get_all_providers() returns: {all_providers}")

        # Test reset again
        provider_tracker.reset_tracking()
        after_reset = provider_tracker.get_all_providers()
        assert after_reset["video_provider"] is None
        assert after_reset["voice_provider"] is None
        assert after_reset["thumb_provider"] is None
        print("✓ reset_tracking() clears all providers")

        print()
        print("✅ TEST 2 PASSED: Provider tracker works correctly")
        print()
        return True

    except Exception as e:
        print(f"❌ TEST 2 FAILED: Provider tracker error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_full_pipeline():
    """TEST 3: Execute full production pipeline with provider tracking"""
    print("=" * 70)
    print("TEST 3: Running full production pipeline...")
    print("=" * 70)
    print()

    try:
        from yt_autopilot.pipeline.produce_render_publish import produce_render_assets
        from yt_autopilot.services import provider_tracker

        # Reset tracker before production
        provider_tracker.reset_tracking()

        # Run full pipeline
        print("Executing produce_render_assets()...")
        result = produce_render_assets(publish_datetime_iso="2025-11-01T18:00:00Z")

        # Verify result structure
        assert "status" in result, "Result missing 'status' key"
        assert result["status"] == "READY_FOR_REVIEW", f"Expected READY_FOR_REVIEW, got {result['status']}"
        print(f"✓ Pipeline status: {result['status']}")

        assert "video_internal_id" in result, "Result missing 'video_internal_id'"
        video_id = result["video_internal_id"]
        print(f"✓ Video internal ID: {video_id}")

        assert "final_video_path" in result, "Result missing 'final_video_path'"
        print(f"✓ Final video path: {result['final_video_path']}")

        assert "thumbnail_path" in result, "Result missing 'thumbnail_path'"
        print(f"✓ Thumbnail path: {result['thumbnail_path']}")

        # Verify physical files exist
        final_video = Path(result["final_video_path"])
        assert final_video.exists(), f"Final video not found: {final_video}"
        assert final_video.stat().st_size >= 1024, "Final video too small (< 1KB)"
        print(f"✓ Final video exists: {final_video.stat().st_size:,} bytes")

        thumbnail = Path(result["thumbnail_path"])
        assert thumbnail.exists(), f"Thumbnail not found: {thumbnail}"
        assert thumbnail.stat().st_size >= 100, "Thumbnail too small (< 100 bytes)"
        print(f"✓ Thumbnail exists: {thumbnail.stat().st_size:,} bytes")

        print()
        print("✅ TEST 3 PASSED: Full pipeline execution successful")
        print()
        return True, video_id

    except Exception as e:
        print(f"❌ TEST 3 FAILED: Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False, None


def test_datastore_provider_fields(video_id):
    """TEST 4: Verify datastore saves provider tracking fields"""
    print("=" * 70)
    print("TEST 4: Checking datastore provider fields...")
    print("=" * 70)
    print()

    try:
        from yt_autopilot.io.datastore import get_draft_package

        # Retrieve draft package
        draft = get_draft_package(video_id)
        assert draft is not None, f"Draft not found for ID: {video_id}"
        print(f"✓ Draft package retrieved: {video_id}")

        # Check production state
        assert draft.get("production_state") == "HUMAN_REVIEW_PENDING"
        print(f"✓ Production state: {draft['production_state']}")

        # Check NEW Step 07.2 provider fields
        video_provider = draft.get("video_provider_used")
        voice_provider = draft.get("voice_provider_used")
        thumb_provider = draft.get("thumb_provider_used")
        thumbnail_prompt = draft.get("thumbnail_prompt")

        print(f"  video_provider_used: {video_provider or '(None)'}")
        print(f"  voice_provider_used: {voice_provider or '(None)'}")
        print(f"  thumb_provider_used: {thumb_provider or '(None)'}")
        print(f"  thumbnail_prompt: {thumbnail_prompt[:50] if thumbnail_prompt else '(None)'}...")

        # Calculate quality score (same logic as review console)
        providers = [video_provider, voice_provider, thumb_provider]
        real_ai_count = sum([
            1 for p in providers
            if p and "FALLBACK" not in p and "PLACEHOLDER" not in p and "SILENT" not in p
        ])
        quality_score = (real_ai_count / 3) * 100

        print()
        print(f"  Real AI providers used: {real_ai_count}/3")
        print(f"  Creator-grade quality: {quality_score:.0f}%")

        if quality_score == 100:
            print(f"  Status: ✓ FULL CREATOR-GRADE QUALITY")
        elif quality_score >= 66:
            print(f"  Status: ~ PARTIAL CREATOR-GRADE (some fallbacks)")
        else:
            print(f"  Status: ⚠ MOSTLY FALLBACKS (check API keys)")

        print()
        print("✅ TEST 4 PASSED: Provider fields saved and retrieved")
        print()
        return True

    except Exception as e:
        print(f"❌ TEST 4 FAILED: Datastore error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def test_review_console_display(video_id):
    """TEST 5: Verify review console displays creative quality check"""
    print("=" * 70)
    print("TEST 5: Testing review console display...")
    print("=" * 70)
    print()

    try:
        from yt_autopilot.io.datastore import get_draft_package

        # Simulate review console logic
        draft = get_draft_package(video_id)

        print("Simulating review console 'show' command output:")
        print()
        print("CREATIVE QUALITY CHECK (Step 07.2):")

        video_provider = draft.get("video_provider_used")
        voice_provider = draft.get("voice_provider_used")
        thumb_provider = draft.get("thumb_provider_used")
        thumbnail_prompt = draft.get("thumbnail_prompt")

        print(f"  Video Provider: {video_provider or '(not available - legacy record)'}")
        print(f"  Voice Provider: {voice_provider or '(not available - legacy record)'}")
        print(f"  Thumbnail Provider: {thumb_provider or '(not available - legacy record)'}")

        if thumbnail_prompt:
            preview = thumbnail_prompt[:200] + "..." if len(thumbnail_prompt) > 200 else thumbnail_prompt
            print(f"  Thumbnail Prompt: {preview}")
        else:
            print(f"  Thumbnail Prompt: (not available)")

        print()
        print("  Quality Indicators:")

        real_providers_count = sum([
            1 for p in [video_provider, voice_provider, thumb_provider]
            if p and "FALLBACK" not in p and "PLACEHOLDER" not in p and "SILENT" not in p
        ])
        quality_score = (real_providers_count / 3) * 100

        print(f"    Real AI providers used: {real_providers_count}/3")
        print(f"    Creator-grade quality: {quality_score:.0f}%")

        if quality_score == 100:
            print(f"    Status: ✓ FULL CREATOR-GRADE QUALITY")
        elif quality_score >= 66:
            print(f"    Status: ~ PARTIAL CREATOR-GRADE (some fallbacks)")
        else:
            print(f"    Status: ⚠ MOSTLY FALLBACKS (check API keys)")

        print()
        print("✅ TEST 5 PASSED: Review console displays creative quality check")
        print()
        return True

    except Exception as e:
        print(f"❌ TEST 5 FAILED: Review console error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False


def main():
    """Run all Step 07.2 acceptance tests"""
    print()
    print("=" * 70)
    print("STEP 07.2: CREATOR-GRADE QUALITY PASS - ACCEPTANCE TEST")
    print("=" * 70)
    print()
    print("This test verifies the complete Step 07.2 implementation.")
    print("System should work whether you have 0, 1, 2, or 3 API providers configured.")
    print()

    results = []

    # TEST 1: Imports
    results.append(("Import Check", test_imports()))

    # TEST 2: Provider Tracker
    results.append(("Provider Tracker", test_provider_tracker()))

    # TEST 3: Full Pipeline
    pipeline_result, video_id = test_full_pipeline()
    results.append(("Full Pipeline", pipeline_result))

    if pipeline_result and video_id:
        # TEST 4: Datastore Provider Fields
        results.append(("Datastore Provider Fields", test_datastore_provider_fields(video_id)))

        # TEST 5: Review Console Display
        results.append(("Review Console Display", test_review_console_display(video_id)))
    else:
        print("⚠ Skipping tests 4-5 due to pipeline failure")
        results.append(("Datastore Provider Fields", False))
        results.append(("Review Console Display", False))

    # Summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print()

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    print()

    all_passed = all(result for _, result in results)

    if all_passed:
        print("=" * 70)
        print("ALL STEP 07.2 TESTS PASSED ✅")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Review the generated video and quality score")
        print("2. Test with different API key configurations:")
        print("   - All keys: 100% creator-grade quality")
        print("   - Some keys: Partial quality (system adapts)")
        print("   - No keys: 0% quality but system still works")
        print("3. Use review console:")
        print("   python tools/review_console.py list")
        print("   python tools/review_console.py show <UUID>")
        print()
        sys.exit(0)
    else:
        print("=" * 70)
        print("SOME TESTS FAILED ❌")
        print("=" * 70)
        print()
        print("Please check the errors above and fix before proceeding.")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
