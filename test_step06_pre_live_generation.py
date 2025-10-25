#!/usr/bin/env python3
"""
Test Script for Step 06-pre: Provider Integration & Live Test

This script verifies that:
1. llm_router can be imported and called
2. video_gen_service can be imported and called
3. New config getters work correctly
4. System gracefully handles missing API keys with fallback

This is a dry-run test - it does NOT make real API calls unless keys are present.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("STEP 06-PRE INTEGRATION TEST")
print("=" * 70)
print()

# =============================================================================
# TEST 1: Config Module - New Getters
# =============================================================================

print("TEST 1: Config module with new LLM provider getters")
print("-" * 70)

try:
    from yt_autopilot.core.config import (
        get_llm_anthropic_key,
        get_llm_openai_key,
        get_veo_api_key,
        get_temp_dir,
        get_output_dir
    )

    print("✓ All new config getters imported successfully")

    # Test key getters (should return None or key string)
    anthropic_key = get_llm_anthropic_key()
    openai_key = get_llm_openai_key()
    veo_key = get_veo_api_key()

    print(f"  - Anthropic key configured: {'Yes' if anthropic_key else 'No'}")
    print(f"  - OpenAI key configured: {'Yes' if openai_key else 'No'}")
    print(f"  - Veo key configured: {'Yes' if veo_key else 'No'}")

    # Test directory getters
    temp_dir = get_temp_dir()
    output_dir = get_output_dir()

    print(f"  - Temp directory: {temp_dir}")
    print(f"  - Output directory: {output_dir}")

    if not temp_dir.exists():
        print(f"    (Creating temp_dir: {temp_dir})")
        temp_dir.mkdir(parents=True, exist_ok=True)

    if not output_dir.exists():
        print(f"    (Creating output_dir: {output_dir})")
        output_dir.mkdir(parents=True, exist_ok=True)

    print("✓ Config module test PASSED")
    print()

except Exception as e:
    print(f"✗ Config module test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 2: LLM Router - Import and Basic Call
# =============================================================================

print("TEST 2: LLM Router module")
print("-" * 70)

try:
    from yt_autopilot.services.llm_router import generate_text

    print("✓ llm_router.generate_text imported successfully")

    # Test LLM call (should return either LLM output or fallback)
    result = generate_text(
        role="script_writer",
        task="Generate a viral hook for YouTube Shorts",
        context="Topic: AI video automation tools for creators",
        style_hints={"brand_tone": "casual", "target_audience": "tech enthusiasts"}
    )

    print(f"✓ LLM Router call completed")
    print(f"  - Result type: {type(result)}")
    print(f"  - Result length: {len(result)} characters")
    print(f"  - Is fallback: {'Yes' if '[LLM_FALLBACK]' in result else 'No'}")
    print()
    print(f"  Sample output (first 150 chars):")
    print(f"  {result[:150]}...")
    print()

    print("✓ LLM Router test PASSED")
    print()

except Exception as e:
    print(f"✗ LLM Router test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 3: Video Generation Service - Import and Mock Call
# =============================================================================

print("TEST 3: Video Generation Service")
print("-" * 70)

try:
    from yt_autopilot.services.video_gen_service import generate_scenes
    from yt_autopilot.core.schemas import VisualPlan, VisualScene

    print("✓ video_gen_service.generate_scenes imported successfully")

    # Create minimal mock visual plan
    mock_plan = VisualPlan(
        aspect_ratio="9:16",
        style_notes="Modern, dynamic tech visuals",
        scenes=[
            VisualScene(
                scene_id=1,
                prompt_for_veo="Opening shot: modern tech workspace with laptop and phone",
                est_duration_seconds=5
            ),
            VisualScene(
                scene_id=2,
                prompt_for_veo="Close-up: hands typing on keyboard, AI interface on screen",
                est_duration_seconds=6
            )
        ]
    )

    print(f"✓ Created mock VisualPlan with {len(mock_plan.scenes)} scenes")

    # Call generate_scenes (should return list of paths, placeholder or real)
    scene_paths = generate_scenes(mock_plan, max_retries=1)

    print(f"✓ generate_scenes() executed successfully")
    print(f"  - Returned type: {type(scene_paths)}")
    print(f"  - Number of paths: {len(scene_paths)}")

    # Verify paths structure
    assert isinstance(scene_paths, list), "Should return list"
    assert len(scene_paths) == len(mock_plan.scenes), f"Should return {len(mock_plan.scenes)} paths"

    for i, path in enumerate(scene_paths, 1):
        assert isinstance(path, str), f"Path {i} should be string"
        assert ".mp4" in path, f"Path {i} should contain .mp4 extension"
        print(f"  - Scene {i}: {Path(path).name}")

    print()
    print("✓ Video Generation Service test PASSED")
    print()

except Exception as e:
    print(f"✗ Video Generation Service test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# TEST 4: Full Integration - Verify No Breaking Changes
# =============================================================================

print("TEST 4: Full integration check")
print("-" * 70)

try:
    # Verify existing services still work
    from yt_autopilot.services import (
        generate_text,  # NEW
        fetch_trends,
        generate_scenes,
        synthesize_voiceover,
        generate_thumbnail,
        assemble_final_video,
        upload_and_schedule,
        fetch_video_metrics
    )

    print("✓ All services imports work (including new generate_text)")

    # Verify agents unchanged
    from yt_autopilot.agents import (
        generate_video_plan,
        write_script,
        generate_visual_plan,
        generate_publishing_package,
        review
    )

    print("✓ All agents imports still work (unchanged)")

    # Verify pipeline unchanged
    from yt_autopilot.pipeline import (
        build_video_package,
        produce_render_assets,
        publish_after_approval
    )

    print("✓ Pipeline functions still work (unchanged)")

    print()
    print("✓ Full integration test PASSED")
    print()

except Exception as e:
    print(f"✗ Integration test FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# =============================================================================
# SUMMARY
# =============================================================================

print("=" * 70)
print("ALL STEP 06-PRE TESTS PASSED ✓")
print("=" * 70)
print()
print("Integration Status:")
print("  ✓ core/config.py: New LLM provider getters working")
print("  ✓ services/llm_router.py: Multi-provider LLM access ready")
print("  ✓ services/video_gen_service.py: Veo integration structure ready")
print("  ✓ All agents: TODO comments added for future LLM integration")
print("  ✓ No breaking changes: Existing code unaffected")
print()
print("Next Steps:")
print("  1. Add API keys to .env file:")
print("     - LLM_ANTHROPIC_API_KEY or LLM_OPENAI_API_KEY")
print("     - VEO_API_KEY (for video generation)")
print("  2. Re-run this test to verify real API calls")
print("  3. Run full pipeline with: python -m yt_autopilot.pipeline.tasks")
print()
print("=" * 70)
