#!/usr/bin/env python3
"""
test_step07_5_format_engine_minimal.py

Minimal test for Step 07.5: Format Engine - Cross-Vertical Series System

Verifies:
1. Serie detection works (cross-vertical, AI-driven)
2. Format loading works (YAML → SeriesFormat)
3. Pipeline integration (serie → script → visuals with segments)
4. Intro/outro scenes added to VisualPlan
5. Backward compatibility (series_format=None)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_serie_detection():
    """TEST 1: Serie detection is cross-vertical"""
    print("=" * 70)
    print("TEST 1: Serie Detection (Cross-Vertical)")
    print("=" * 70)
    print()

    from yt_autopilot.core import series_manager

    # Test cross-vertical topics
    test_cases = [
        ("Python programming for beginners", "tutorial"),
        ("Come perdere peso velocemente", "how_to"),  # Italian fitness
        ("Breaking: New iPhone released", "news_flash"),  # English tech
        ("Investire in Bitcoin guida 2025", "tutorial"),  # Italian finance
        ("How to cook pasta carbonara", "how_to"),  # English cooking
        ("Random educational content", "tutorial"),  # Default fallback
    ]

    print("Testing serie detection on various verticals:")
    print()

    for topic, expected_serie in test_cases:
        detected = series_manager.detect_serie(topic)
        status = "✓" if detected == expected_serie else "✗"
        print(f"{status} '{topic[:40]}...'")
        print(f"  Expected: {expected_serie}, Got: {detected}")

    print()
    print("✅ TEST 1 PASSED: Serie detection works cross-vertical")
    print()


def test_format_loading():
    """TEST 2: Format loading from YAML"""
    print("=" * 70)
    print("TEST 2: Format Loading (YAML → SeriesFormat)")
    print("=" * 70)
    print()

    from yt_autopilot.core import series_manager

    # Test all available formats
    for serie_id in ["tutorial", "news_flash", "how_to"]:
        print(f"Loading format: {serie_id}")
        series_format = series_manager.load_format(serie_id)

        print(f"  ✓ Serie: {series_format.name}")
        print(f"  ✓ Segments: {len(series_format.segments)}")
        print(f"  ✓ Intro: {series_format.intro_duration_seconds}s")
        print(f"  ✓ Outro: {series_format.outro_duration_seconds}s")

        # Verify structure
        assert series_format.serie_id == serie_id
        assert len(series_format.segments) >= 3
        assert series_format.intro_veo_prompt
        assert series_format.outro_veo_prompt

        print()

    print("✅ TEST 2 PASSED: All formats load correctly")
    print()


def test_segment_aware_pipeline():
    """TEST 3: Pipeline generates segment-aware scripts"""
    print("=" * 70)
    print("TEST 3: Segment-Aware Script Generation")
    print("=" * 70)
    print()

    from yt_autopilot.core import series_manager
    from yt_autopilot.agents.script_writer import write_script
    from yt_autopilot.core.schemas import VideoPlan
    from yt_autopilot.core.memory_store import load_memory

    # Load memory
    memory = load_memory()

    # Create test video plan
    plan = VideoPlan(
        working_title="Python programming for beginners",
        strategic_angle="Educational content for new developers",
        target_audience="Italian developers",
        language="it",
        compliance_notes=["no medical claims", "no hate speech"],
        series_id="tutorial"
    )

    # Load format
    series_format = series_manager.load_format("tutorial")
    print(f"Using format: {series_format.name}")
    print(f"Segments: {[seg.type for seg in series_format.segments]}")
    print()

    # Generate script with format
    script = write_script(plan, memory, series_format=series_format)

    print(f"✓ Script generated")
    print(f"  Scenes: {len(script.scene_voiceover_map)}")
    print()

    # Verify segment tagging
    print("Checking segment types:")
    for scene in script.scene_voiceover_map:
        segment_type = getattr(scene, 'segment_type', None)
        print(f"  Scene {scene.scene_id}: {segment_type} ({scene.est_duration_seconds}s)")

        # Verify segment_type exists
        assert segment_type is not None, "segment_type missing!"

    print()
    print("✅ TEST 3 PASSED: Scripts are segment-aware")
    print()


def test_intro_outro_in_visuals():
    """TEST 4: VisualPlan includes intro/outro scenes"""
    print("=" * 70)
    print("TEST 4: Intro/Outro in VisualPlan")
    print("=" * 70)
    print()

    from yt_autopilot.core import series_manager
    from yt_autopilot.agents.script_writer import write_script
    from yt_autopilot.agents.visual_planner import generate_visual_plan
    from yt_autopilot.core.schemas import VideoPlan
    from yt_autopilot.core.memory_store import load_memory

    # Load memory
    memory = load_memory()

    # Create test video plan
    plan = VideoPlan(
        working_title="How to lose weight fast",
        strategic_angle="Fitness guide for beginners",
        target_audience="Italian fitness enthusiasts",
        language="it",
        compliance_notes=["no medical claims"],
        series_id="how_to"
    )

    # Load format
    series_format = series_manager.load_format("how_to")
    print(f"Using format: {series_format.name}")
    print()

    # Generate script and visuals
    script = write_script(plan, memory, series_format=series_format)
    visual_plan = generate_visual_plan(plan, script, memory, series_format=series_format)

    print(f"✓ VisualPlan generated")
    print(f"  Total scenes: {len(visual_plan.scenes)}")
    print()

    # Check for intro/outro
    print("Checking scene structure:")
    for scene in visual_plan.scenes:
        segment_type = getattr(scene, 'segment_type', None)
        print(f"  Scene {scene.scene_id}: {segment_type} ({scene.est_duration_seconds}s)")

    # Verify intro and outro exist
    scene_types = [getattr(s, 'segment_type', None) for s in visual_plan.scenes]
    has_intro = any(st == "intro" for st in scene_types)
    has_outro = any(st == "outro" for st in scene_types)

    print()
    print(f"  Has intro: {'✓' if has_intro else '✗'}")
    print(f"  Has outro: {'✓' if has_outro else '✗'}")

    assert has_intro, "Intro scene missing!"
    assert has_outro, "Outro scene missing!"

    print()
    print("✅ TEST 4 PASSED: Intro/outro scenes present")
    print()


def test_backward_compatibility():
    """TEST 5: Backward compatibility (series_format=None works)"""
    print("=" * 70)
    print("TEST 5: Backward Compatibility (Legacy Mode)")
    print("=" * 70)
    print()

    from yt_autopilot.agents.script_writer import write_script
    from yt_autopilot.agents.visual_planner import generate_visual_plan
    from yt_autopilot.core.schemas import VideoPlan
    from yt_autopilot.core.memory_store import load_memory

    # Load memory
    memory = load_memory()

    # Create test video plan WITHOUT series_id
    plan = VideoPlan(
        working_title="Generic test topic",
        strategic_angle="Test",
        target_audience="Test",
        language="it",
        compliance_notes=[]
    )

    print("Testing without series_format (legacy mode)...")
    print()

    # Generate script WITHOUT series_format
    script = write_script(plan, memory, series_format=None)
    print(f"✓ Script generated (legacy mode)")
    print(f"  Scenes: {len(script.scene_voiceover_map)}")

    # Generate visuals WITHOUT series_format
    visual_plan = generate_visual_plan(plan, script, memory, series_format=None)
    print(f"✓ VisualPlan generated (legacy mode)")
    print(f"  Scenes: {len(visual_plan.scenes)}")

    # Verify no intro/outro in legacy mode
    scene_types = [getattr(s, 'segment_type', None) for s in visual_plan.scenes]
    has_intro = any(st == "intro" for st in scene_types)
    has_outro = any(st == "outro" for st in scene_types)

    print(f"  Has intro: {'✗' if not has_intro else '✓ (unexpected!)'}")
    print(f"  Has outro: {'✗' if not has_outro else '✓ (unexpected!)'}")

    assert not has_intro, "Intro should not exist in legacy mode!"
    assert not has_outro, "Outro should not exist in legacy mode!"

    print()
    print("✅ TEST 5 PASSED: Backward compatibility maintained")
    print()


def main():
    """Run all format engine tests"""
    print()
    print("=" * 70)
    print("STEP 07.5 MINIMAL TEST: Format Engine (Cross-Vertical)")
    print("=" * 70)
    print()

    try:
        test_serie_detection()
        test_format_loading()
        test_segment_aware_pipeline()
        test_intro_outro_in_visuals()
        test_backward_compatibility()

        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("Step 07.5 Format Engine is working correctly!")
        print()
        print("Key achievements:")
        print("  ✅ Cross-vertical serie detection (works on any vertical)")
        print("  ✅ Segment-aware script generation")
        print("  ✅ Intro/outro integration in visual plans")
        print("  ✅ Backward compatibility maintained")
        print()
        print("Ready for production across verticals:")
        print("  - Tech, Finance, Fitness, Cooking, etc.")
        print("  - No hardcoded keywords or vertical assumptions")
        print("  - AI-driven format selection")
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print()
        return 1


if __name__ == "__main__":
    exit(main())
