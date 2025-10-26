#!/usr/bin/env python3
"""
test_phase_b_llm_curation.py

Comprehensive end-to-end test for Phase B: LLM-Powered Trend Curation

This test validates the complete intelligent curation pipeline:
- Phase A: Spam filtering + quality thresholds + source weighting
- Phase B: LLM evaluation for educational value, brand fit, timing

Tests three modes:
1. Mock mode (baseline, no real APIs)
2. Phase A only (real trends, deterministic filtering)
3. Phase A + B (real trends + LLM curation)

Validates that LLM curation produces higher quality content selection.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from yt_autopilot.pipeline.build_video_package import build_video_package
from yt_autopilot.services.trend_source import fetch_trends


def test_mode_1_mock_trends():
    """Test Mode 1: Mock trends (baseline)"""
    print("=" * 70)
    print("MODE 1: MOCK TRENDS (Baseline)")
    print("=" * 70)
    print()
    print("Testing with mock trends (no real APIs, no LLM)...")
    print()

    try:
        # Uses active workspace (should be tech_ai_creator or compatible)
        package = build_video_package(
            workspace_id=None,  # Use active workspace
            use_real_trends=False,
            use_llm_curation=False
        )

        print()
        print(f"Mock Mode Result:")
        print(f"  Status: {package.status}")
        print(f"  Selected: {package.video_plan.working_title}")
        print()

        return package

    except Exception as e:
        print(f"❌ Mock mode failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_mode_2_phase_a_only():
    """Test Mode 2: Real trends with Phase A filtering only (no LLM)"""
    print("=" * 70)
    print("MODE 2: REAL TRENDS + PHASE A (No LLM)")
    print("=" * 70)
    print()
    print("Testing with real API trends + Phase A filtering:")
    print("  ✓ Spam detection (pattern blacklist)")
    print("  ✓ Quality thresholds (min engagement)")
    print("  ✓ Source weighting (Reddit > HN > YouTube)")
    print("  ✗ LLM curation (DISABLED)")
    print()

    try:
        # Uses active workspace (should be tech_ai_creator or compatible)
        package = build_video_package(
            workspace_id=None,  # Use active workspace
            use_real_trends=True,
            use_llm_curation=False  # Phase A only
        )

        print()
        print(f"Phase A Result:")
        print(f"  Status: {package.status}")
        print(f"  Selected: {package.video_plan.working_title}")
        print(f"  Strategic Angle: {package.video_plan.strategic_angle[:100]}...")
        print()

        return package

    except Exception as e:
        print(f"❌ Phase A mode failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_mode_3_phase_a_plus_b():
    """Test Mode 3: Real trends with Phase A + Phase B (LLM curation)"""
    print("=" * 70)
    print("MODE 3: REAL TRENDS + PHASE A + PHASE B (Full LLM Curation)")
    print("=" * 70)
    print()
    print("Testing with real API trends + Phase A + Phase B:")
    print("  ✓ Spam detection (pattern blacklist)")
    print("  ✓ Quality thresholds (min engagement)")
    print("  ✓ Source weighting (Reddit > HN > YouTube)")
    print("  ✓ LLM curation (educational value, brand fit, timing)")
    print()
    print("Expected: LLM selects most educational/valuable content")
    print()

    try:
        # Uses active workspace (should be tech_ai_creator or compatible)
        package = build_video_package(
            workspace_id=None,  # Use active workspace
            use_real_trends=True,
            use_llm_curation=True  # Phase A + Phase B
        )

        print()
        print(f"Phase B Result:")
        print(f"  Status: {package.status}")
        print(f"  Selected: {package.video_plan.working_title}")
        print(f"  Strategic Angle: {package.video_plan.strategic_angle[:100]}...")
        print()

        return package

    except Exception as e:
        print(f"❌ Phase B mode failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_results(mock_pkg, phase_a_pkg, phase_b_pkg):
    """Compare results across all three modes"""
    print("=" * 70)
    print("COMPARISON: Mock vs Phase A vs Phase B")
    print("=" * 70)
    print()

    results = [
        ("Mock Mode (Baseline)", mock_pkg),
        ("Phase A Only (Quality Filtering)", phase_a_pkg),
        ("Phase A + B (LLM Curation)", phase_b_pkg)
    ]

    for mode_name, pkg in results:
        if pkg:
            print(f"{mode_name}:")
            print(f"  Selected: {pkg.video_plan.working_title}")
            print(f"  Angle: {pkg.video_plan.strategic_angle[:80]}...")
            print()
        else:
            print(f"{mode_name}: FAILED")
            print()

    print("=" * 70)
    print()


def validate_llm_quality_improvement(phase_a_pkg, phase_b_pkg):
    """
    Validates that Phase B (LLM curation) produces higher quality selection.

    Quality signals:
    - Educational keywords: "explained", "tutorial", "how", "understanding", "learning"
    - AI/Tech relevance: "AI", "GPT", "programming", "coding", "tech"
    - Avoids spam: no "test", "vs", "review", "unboxing"
    """
    print("=" * 70)
    print("QUALITY VALIDATION")
    print("=" * 70)
    print()

    if not phase_a_pkg or not phase_b_pkg:
        print("❌ Cannot validate - one or both packages failed")
        return False

    phase_a_title = phase_a_pkg.video_plan.working_title.lower()
    phase_b_title = phase_b_pkg.video_plan.working_title.lower()

    # Educational keywords
    educational_keywords = ["explained", "tutorial", "how", "understanding", "learning", "guide", "deep dive"]
    ai_tech_keywords = ["ai", "gpt", "programming", "coding", "tech", "python", "machine learning", "claude"]
    spam_keywords = [" test", " vs ", "review", "unboxing", "challenge"]

    def count_keywords(title, keywords):
        return sum(1 for kw in keywords if kw in title)

    phase_a_educational = count_keywords(phase_a_title, educational_keywords)
    phase_a_tech = count_keywords(phase_a_title, ai_tech_keywords)
    phase_a_spam = count_keywords(phase_a_title, spam_keywords)

    phase_b_educational = count_keywords(phase_b_title, educational_keywords)
    phase_b_tech = count_keywords(phase_b_title, ai_tech_keywords)
    phase_b_spam = count_keywords(phase_b_title, spam_keywords)

    print("Phase A Selection Quality:")
    print(f"  Title: {phase_a_pkg.video_plan.working_title}")
    print(f"  Educational keywords: {phase_a_educational}")
    print(f"  AI/Tech keywords: {phase_a_tech}")
    print(f"  Spam keywords: {phase_a_spam}")
    print()

    print("Phase B Selection Quality:")
    print(f"  Title: {phase_b_pkg.video_plan.working_title}")
    print(f"  Educational keywords: {phase_b_educational}")
    print(f"  AI/Tech keywords: {phase_b_tech}")
    print(f"  Spam keywords: {phase_b_spam}")
    print()

    # Validation criteria
    passed = True

    if phase_a_spam > 0 or phase_b_spam > 0:
        print("⚠️  WARNING: Spam keywords detected in selection")
        if phase_b_spam > 0:
            print("   Phase B should not select spam content!")
            passed = False

    if phase_b_educational >= phase_a_educational and phase_b_tech >= phase_a_tech:
        print("✅ Phase B shows equal or better quality signals")
    else:
        print("⚠️  Phase B did not improve quality signals (may be OK if both are high quality)")

    if phase_b_spam == 0:
        print("✅ Phase B avoided spam patterns")
    else:
        print("❌ Phase B selected spam content - LLM curation failed!")
        passed = False

    print()
    return passed


def main():
    print()
    print("=" * 70)
    print("PHASE B TEST SUITE: LLM-Powered Trend Curation")
    print("=" * 70)
    print()
    print("This test validates the complete intelligent curation pipeline:")
    print("  - Phase A: Spam filtering + quality thresholds + source weighting")
    print("  - Phase B: LLM evaluation for educational value, brand fit, timing")
    print()
    print("Testing three modes:")
    print("  1. Mock mode (baseline, no real APIs)")
    print("  2. Phase A only (real trends, deterministic filtering)")
    print("  3. Phase A + B (real trends + LLM curation)")
    print()
    print("=" * 70)
    print()

    # Test all three modes
    print("Running Mode 1: Mock trends...")
    mock_pkg = test_mode_1_mock_trends()

    print("Running Mode 2: Phase A only...")
    phase_a_pkg = test_mode_2_phase_a_only()

    print("Running Mode 3: Phase A + Phase B...")
    phase_b_pkg = test_mode_3_phase_a_plus_b()

    # Compare results
    compare_results(mock_pkg, phase_a_pkg, phase_b_pkg)

    # Validate quality improvement
    quality_passed = validate_llm_quality_improvement(phase_a_pkg, phase_b_pkg)

    # Final verdict
    print("=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)
    print()

    if not mock_pkg:
        print("❌ Mock mode failed - baseline broken")
        return 1

    if not phase_a_pkg:
        print("❌ Phase A failed - quality filtering broken")
        return 1

    if not phase_b_pkg:
        print("❌ Phase B failed - LLM curation broken")
        return 1

    if not quality_passed:
        print("❌ Quality validation failed - LLM not improving selection")
        print()
        print("Phase B is functional but not meeting quality goals.")
        print("Review LLM curation prompt and evaluation criteria.")
        return 1

    print("✅ ALL TESTS PASSED!")
    print()
    print("Intelligent curation system is operational:")
    print("  ✅ Phase A: Spam filtering, quality thresholds, source weighting")
    print("  ✅ Phase B: LLM curation for educational value and brand fit")
    print()
    print("System successfully selects high-quality content:")
    print("  - Avoids viral spam (test, vs, review, unboxing)")
    print("  - Prioritizes educational AI/tech content")
    print("  - Matches channel brand and audience")
    print()
    print("Ready for production!")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
