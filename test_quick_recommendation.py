#!/usr/bin/env python3
"""
Test rapido per vedere cosa raccomanda il sistema con intelligent curation
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from yt_autopilot.services.trend_source import fetch_trends
from yt_autopilot.agents.trend_hunter import generate_video_plan
from yt_autopilot.core.memory_store import load_memory
from yt_autopilot.services.llm_trend_curator import curate_trends_with_llm
from yt_autopilot.services.llm_router import generate_text


def test_recommendation():
    print()
    print("=" * 70)
    print("TEST RACCOMANDAZIONE VIDEO - Sistema Intelligent Curation")
    print("=" * 70)
    print()

    # Carica memoria
    memory = load_memory()

    # Fase 1: Fetch trends con Phase A filtering
    print("FASE 1: Fetching trends con Phase A filtering...")
    print("  - Spam detection")
    print("  - Quality thresholds (Reddit >500 upvotes, HN >100 points)")
    print("  - Deduplication")
    print()

    trends = fetch_trends(vertical_id="tech_ai", use_real_apis=True)

    print(f"✓ Fetched {len(trends)} quality-filtered trends")
    print()

    # Mostra top 10 trends per source
    print("TOP 10 TRENDS (dopo Phase A filtering):")
    print()

    reddit_trends = [t for t in trends if "reddit" in t.source.lower()]
    hn_trends = [t for t in trends if "hackernews" in t.source.lower()]
    youtube_trends = [t for t in trends if "youtube" in t.source.lower()]

    print(f"Reddit Trends ({len(reddit_trends)} total):")
    for i, trend in enumerate(reddit_trends[:5], 1):
        print(f"  [{i}] {trend.keyword[:70]}")
        print(f"      Momentum: {trend.momentum_score:.2f}")
    print()

    print(f"Hacker News Trends ({len(hn_trends)} total):")
    for i, trend in enumerate(hn_trends[:5], 1):
        print(f"  [{i}] {trend.keyword[:70]}")
        print(f"      Momentum: {trend.momentum_score:.2f}")
    print()

    print(f"YouTube Trends ({len(youtube_trends)} total):")
    for i, trend in enumerate(youtube_trends[:3], 1):
        print(f"  [{i}] {trend.keyword[:70]}")
        print(f"      Momentum: {trend.momentum_score:.2f}")
    print()

    # Fase 2: Selezione SENZA LLM (Phase A only)
    print("=" * 70)
    print("RACCOMANDAZIONE SENZA LLM (Phase A only)")
    print("=" * 70)
    print()

    video_plan_a = generate_video_plan(trends, memory)

    print(f"✅ Video raccomandato (Phase A):")
    print(f"   Titolo: {video_plan_a.working_title}")
    print(f"   Perché: {video_plan_a.strategic_angle[:150]}...")
    print()

    # Fase 3: Selezione CON LLM (Phase A + B)
    print("=" * 70)
    print("RACCOMANDAZIONE CON LLM CURATION (Phase A + B)")
    print("=" * 70)
    print()

    print("Running LLM curation...")
    print("  LLM valuterà i trends per:")
    print("    - Educational value (40%)")
    print("    - Brand fit (25%)")
    print("    - Timing relevance (20%)")
    print("    - Viral potential (15%)")
    print()

    try:
        curated_trends = curate_trends_with_llm(
            trends=trends,
            vertical_id="tech_ai",
            memory=memory,
            llm_generate_fn=generate_text,
            max_trends_to_evaluate=min(30, len(trends)),
            top_n=10
        )

        print(f"✓ LLM curation complete: {len(trends)} → {len(curated_trends)} trends")
        print()

        print("Top 10 trends curati da LLM:")
        for i, trend in enumerate(curated_trends, 1):
            print(f"  [{i}] {trend.keyword[:70]}")
            print(f"      Source: {trend.source}, Momentum: {trend.momentum_score:.2f}")
        print()

        # Selezione finale con TrendHunter
        video_plan_b = generate_video_plan(curated_trends, memory)

        print(f"✅ Video raccomandato (Phase A + B):")
        print(f"   Titolo: {video_plan_b.working_title}")
        print(f"   Perché: {video_plan_b.strategic_angle[:150]}...")
        print()

    except Exception as e:
        print(f"❌ LLM curation fallita: {e}")
        video_plan_b = None

    # Confronto
    print("=" * 70)
    print("CONFRONTO RACCOMANDAZIONI")
    print("=" * 70)
    print()

    print("Phase A only (deterministic filtering):")
    print(f"  → {video_plan_a.working_title[:80]}")
    print()

    if video_plan_b:
        print("Phase A + B (LLM curation):")
        print(f"  → {video_plan_b.working_title[:80]}")
        print()

        if video_plan_a.working_title != video_plan_b.working_title:
            print("✅ LLM ha selezionato un video DIVERSO (più educativo/brand fit)")
        else:
            print("ℹ️  LLM ha confermato la stessa scelta (entrambi di alta qualità)")
    else:
        print("Phase A + B: FAILED (LLM non disponibile)")

    print()
    print("=" * 70)
    print()


if __name__ == "__main__":
    test_recommendation()
