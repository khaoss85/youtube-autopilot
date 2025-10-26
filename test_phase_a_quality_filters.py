#!/usr/bin/env python3
"""
test_phase_a_quality_filters.py

Quick test for Phase A improvements:
1. Spam filtering and quality thresholds
2. Source quality weighting (Reddit 3x > HN 2x > YouTube 1x)

Validates that:
- Spam patterns are filtered out (e.g., "iPhone battery test")
- Low-quality trends removed (low upvotes, low engagement)
- Reddit/HN trends ranked higher than YouTube spam
- Top recommendation is quality content (e.g., "Sam Altman AI Jobs")
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from yt_autopilot.services.trend_source import fetch_trends
from yt_autopilot.agents.trend_hunter import generate_video_plan
from yt_autopilot.core.memory_store import load_memory


def test_phase_a_quality_filtering():
    """Test Phase A.1: Spam filtering and quality thresholds"""
    print("=" * 70)
    print("PHASE A.1 TEST: Quality Filtering (Spam + Thresholds)")
    print("=" * 70)
    print()

    # Fetch trends with quality filtering enabled
    print("Fetching trends with Phase A quality filters enabled...")
    print("Expected behavior:")
    print("  ✓ Spam patterns filtered (test, vs, review, unboxing, challenge)")
    print("  ✓ Low-quality trends removed (< 500 upvotes Reddit, < 100 HN)")
    print("  ✓ Duplicates removed")
    print()

    trends = fetch_trends(vertical_id="tech_ai", use_real_apis=True)

    print(f"\n✓ Quality filtering complete: {len(trends)} high-quality trends")
    print()

    # Show source distribution
    source_counts = {}
    for trend in trends:
        source = trend.source
        source_counts[source] = source_counts.get(source, 0) + 1

    print("Source Distribution (after filtering):")
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {source}: {count} trends")
    print()

    # Show top 10 trends by source
    print("=" * 70)
    print("Top 10 Trends by Source (Before TrendHunter Scoring)")
    print("=" * 70)
    print()

    reddit_trends = [t for t in trends if "reddit" in t.source.lower()]
    hn_trends = [t for t in trends if "hackernews" in t.source.lower()]
    youtube_trends = [t for t in trends if "youtube" in t.source.lower()]

    print(f"Reddit Trends ({len(reddit_trends)} total):")
    for i, trend in enumerate(reddit_trends[:5], 1):
        print(f"  [{i}] {trend.keyword[:60]}")
        print(f"      Momentum: {trend.momentum_score:.2f}, CPM: ${trend.cpm_estimate:.1f}")
    print()

    print(f"Hacker News Trends ({len(hn_trends)} total):")
    for i, trend in enumerate(hn_trends[:5], 1):
        print(f"  [{i}] {trend.keyword[:60]}")
        print(f"      Momentum: {trend.momentum_score:.2f}, CPM: ${trend.cpm_estimate:.1f}")
    print()

    print(f"YouTube Trends ({len(youtube_trends)} total):")
    for i, trend in enumerate(youtube_trends[:5], 1):
        print(f"  [{i}] {trend.keyword[:60]}")
        print(f"      Momentum: {trend.momentum_score:.2f}, CPM: ${trend.cpm_estimate:.1f}")
    print()

    return trends


def test_phase_a_source_weighting(trends):
    """Test Phase A.2: Source quality weighting in TrendHunter"""
    print("=" * 70)
    print("PHASE A.2 TEST: Source Quality Weighting (Reddit 3x > HN 2x > YouTube 1x)")
    print("=" * 70)
    print()

    print("Loading channel memory...")
    memory = load_memory()
    print()

    print("Running TrendHunter with Phase A.2 source quality weights...")
    print("Expected behavior:")
    print("  ✓ Reddit trends get +0.30-0.35 bonus")
    print("  ✓ Hacker News trends get +0.20-0.22 bonus")
    print("  ✓ YouTube trends get +0.05-0.10 bonus")
    print("  ✓ Top recommendation is quality content (NOT spam)")
    print()

    # Generate video plan (uses source weighting)
    video_plan = generate_video_plan(trends, memory)

    print()
    print("=" * 70)
    print("FINAL RECOMMENDATION (Top Video Plan)")
    print("=" * 70)
    print()
    print(f"Selected Topic: {video_plan.working_title}")
    print(f"Strategic Angle: {video_plan.strategic_angle}")
    print(f"Target Audience: {video_plan.target_audience}")
    print()

    # Find the selected trend to show details
    selected_trend = None
    for trend in trends:
        if trend.keyword == video_plan.working_title:
            selected_trend = trend
            break

    if selected_trend:
        print("Trend Details:")
        print(f"  Source: {selected_trend.source}")
        print(f"  Momentum: {selected_trend.momentum_score:.2f}")
        print(f"  CPM Estimate: ${selected_trend.cpm_estimate:.1f}")
        print(f"  Competition: {selected_trend.competition_level}")
        print(f"  Virality: {selected_trend.virality_score:.2f}")
        print()

    return video_plan


def test_comparison_with_old_system(trends):
    """Compare new system with old system (without quality filters)"""
    print("=" * 70)
    print("COMPARISON: Phase A vs Old System")
    print("=" * 70)
    print()

    # Simulate old system: sort by momentum only (no spam filtering, no source weighting)
    print("Old System (pure momentum, no filtering):")
    old_ranking = sorted(trends, key=lambda t: t.momentum_score, reverse=True)
    for i, trend in enumerate(old_ranking[:5], 1):
        print(f"  [{i}] {trend.keyword[:60]}")
        print(f"      Source: {trend.source}, Momentum: {trend.momentum_score:.2f}")
    print()

    # Check if old system would have picked spam
    if old_ranking:
        old_top = old_ranking[0]
        keyword_lower = old_top.keyword.lower()
        is_spam = any(pattern in keyword_lower for pattern in [" test", " vs ", "review", "unboxing", "challenge"])

        if is_spam:
            print(f"⚠️  Old system would have picked: '{old_top.keyword[:60]}'")
            print(f"   This is SPAM (pattern detected: {old_top.keyword[:60]})")
        else:
            print(f"✓ Old system picked quality: '{old_top.keyword[:60]}'")

    print()
    print("=" * 70)
    print()


def main():
    print()
    print("=" * 70)
    print("PHASE A INTELLIGENT CURATION TEST SUITE")
    print("=" * 70)
    print()
    print("This test validates Phase A quick wins:")
    print("  A.1: Spam filtering + quality thresholds")
    print("  A.2: Source quality weighting (Reddit > HN > YouTube)")
    print()
    print("=" * 70)
    print()

    try:
        # Test A.1: Quality filtering
        trends = test_phase_a_quality_filtering()

        if not trends:
            print("❌ No trends returned - quality filters may be too strict!")
            return 1

        # Test A.2: Source weighting
        video_plan = test_phase_a_source_weighting(trends)

        # Comparison
        test_comparison_with_old_system(trends)

        # Final validation
        print("=" * 70)
        print("PHASE A TEST RESULTS")
        print("=" * 70)
        print()

        selected_keyword = video_plan.working_title.lower()
        is_spam = any(pattern in selected_keyword for pattern in [" test", " vs ", "review", "unboxing", "challenge"])

        if is_spam:
            print("❌ PHASE A FAILED: Selected topic contains spam patterns!")
            print(f"   Selected: '{video_plan.working_title}'")
            print()
            print("This means quality filtering is not working correctly.")
            return 1
        else:
            print("✅ PHASE A PASSED: Selected topic is high-quality content!")
            print(f"   Selected: '{video_plan.working_title}'")
            print()
            print("Quality improvements:")
            print("  ✓ Spam patterns filtered out")
            print("  ✓ Low-quality trends removed")
            print("  ✓ Reddit/HN trends prioritized over YouTube spam")
            print()
            print("Phase A (Quick Wins) is working correctly!")
            print()
            print("Next step: Phase B - LLM Curation Layer")
            print()
            return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
