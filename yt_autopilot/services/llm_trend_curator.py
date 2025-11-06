"""
LLM-Powered Trend Curator Service

Phase B: Intelligent curation using LLM to evaluate trends for quality and brand fit.

This service sits between trend_source (raw trends) and trend_hunter (final selection):
1. trend_source fetches + filters → ~25 quality trends
2. llm_trend_curator evaluates → top 10 curated trends
3. trend_hunter scores + selects → final video plan

The LLM acts as a "human-like" curator, evaluating:
- Educational value (avoid entertainment spam)
- Brand fit (matches channel tone/audience)
- Timing relevance (is this happening NOW?)
- Viral potential (will this get views?)
- Content originality (not overdone)

Cost: ~$0.01 per curation (cheap for high-value filtering)
"""

from typing import List, Dict, Optional
from yt_autopilot.core.schemas import TrendCandidate
from yt_autopilot.core.logger import logger, log_fallback
import json


def build_curation_prompt(
    trends: List[TrendCandidate],
    vertical_id: str,
    memory: Dict,
    max_trends_to_evaluate: int = 30
) -> str:
    """
    Builds LLM prompt for trend curation.

    Phase B.1: Prompt design for intelligent trend evaluation

    Args:
        trends: List of quality-filtered trends (from Phase A)
        vertical_id: Content vertical ('tech_ai', 'finance', etc.)
        memory: Channel memory (brand_tone, recent_titles, banned_topics)
        max_trends_to_evaluate: How many trends to send to LLM (default: 30)

    Returns:
        Formatted prompt string for LLM evaluation

    Prompt Strategy:
        - Clear task: "You are a YouTube content curator"
        - Context: Channel brand, vertical, recent content
        - Trends: Numbered list with source, momentum, why_hot
        - Evaluation criteria: Educational value, brand fit, timing, virality
        - Output format: JSON array of top 10 trend indices
    """
    # Get channel context
    brand_tone = memory.get("brand_tone", "Direct, energetic Italian tech content creator")
    recent_titles = memory.get("recent_titles", [])
    banned_topics = memory.get("banned_topics", [])
    target_language = memory.get("target_language", "en")

    # Language mapping for explicit instruction (pattern from narrative_architect)
    language_names = {
        "en": "ENGLISH",
        "it": "ITALIAN",
        "es": "SPANISH",
        "fr": "FRENCH",
        "de": "GERMAN",
        "pt": "PORTUGUESE"
    }
    language_instruction = language_names.get(target_language.lower(), target_language.upper())

    # Limit trends to top N by momentum (pre-filter before LLM)
    trends_to_evaluate = sorted(trends, key=lambda t: t.momentum_score, reverse=True)[:max_trends_to_evaluate]

    # Build trend list for LLM
    trends_text = []
    for i, trend in enumerate(trends_to_evaluate, 1):
        trend_info = f"""
[{i}] {trend.keyword}
    Source: {trend.source}
    Momentum: {trend.momentum_score:.2f} | CPM: ${trend.cpm_estimate:.1f}
    Competition: {trend.competition_level} | Virality: {trend.virality_score:.2f}
    Why Hot: {trend.why_hot}
"""
        trends_text.append(trend_info.strip())

    trends_list = "\n\n".join(trends_text)

    # Build recent content context
    recent_context = ""
    if recent_titles:
        recent_context = f"""
RECENT VIDEOS (avoid similar topics):
{chr(10).join(f'- {title}' for title in recent_titles[:10])}
"""

    # Build banned topics context
    banned_context = ""
    if banned_topics:
        banned_context = f"""
BANNED TOPICS (never select):
{', '.join(banned_topics)}
"""

    # Vertical-specific guidance
    vertical_guidance = {
        "tech_ai": """
VERTICAL: Tech & AI
AUDIENCE: Tech-savvy audience interested in AI, programming, automation, productivity
CONTENT STYLE: Educational, practical tutorials, AI news analysis, coding tips
AVOID: Product reviews, unboxing, gaming content, celebrity gossip
PRIORITIZE: AI breakthroughs, programming tutorials, tech industry news, automation tools
""",
        "finance": """
VERTICAL: Finance & Investing
AUDIENCE: People interested in passive income, investing, financial freedom
CONTENT STYLE: Financial advice, market analysis, investment strategies
AVOID: Get-rich-quick schemes, crypto pumps, gambling
PRIORITIZE: Market trends, investment education, personal finance tips
""",
        "gaming": """
VERTICAL: Gaming
AUDIENCE: Gamers, esports fans, game enthusiasts
CONTENT STYLE: Gameplay highlights, gaming news, tips & tricks
AVOID: Unrelated tech content, political content
PRIORITIZE: New game releases, esports updates, gaming tutorials
""",
        "education": """
VERTICAL: Education
AUDIENCE: Learners, students, curious minds
CONTENT STYLE: Tutorials, deep dives, educational content
AVOID: Clickbait, superficial content, entertainment spam
PRIORITIZE: In-depth explanations, educational tutorials, learning resources
"""
    }

    vertical_guide = vertical_guidance.get(vertical_id, vertical_guidance["tech_ai"])

    # Build final prompt
    prompt = f"""You are an expert YouTube content curator for a {vertical_id} channel.

CHANNEL BRAND IDENTITY:
{brand_tone}

{vertical_guide.strip()}

⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
ALL OUTPUT MUST BE IN {language_instruction}. The "reasoning" field MUST be written in {language_instruction}.
DO NOT mix languages. If you see examples in other languages below, IGNORE their language and write in {language_instruction}.

YOUR TASK:
Evaluate the following {len(trends_to_evaluate)} trending topics and select the TOP 10 that would make the best YouTube videos for this channel.

EVALUATION CRITERIA (in priority order):
1. EDUCATIONAL VALUE (40%): Does this teach something valuable? Avoid pure entertainment/spam
2. BRAND FIT (25%): Does this match our channel's tone and audience?
3. TIMING RELEVANCE (20%): Is this happening NOW? Is it timely?
4. VIRAL POTENTIAL (15%): Will this topic attract views and engagement?

CRITICAL SOURCE QUALITY RULES:
🔥 STRONGLY PREFER Reddit and Hacker News trends (reddit_*, hackernews sources)
🔥 Reddit/HN = High-quality, community-curated, educational content
⚠️  AVOID YouTube trends unless exceptionally educational
⚠️  YouTube Shorts/Search = Usually spam, low educational value

QUALITY SIGNALS TO PRIORITIZE:
✓✓✓ Reddit/Hacker News sources (TOP PRIORITY - these are curated by tech communities)
✓✓ High momentum AND from Reddit/HN (momentum > 0.5 + reddit/hackernews source)
✓ Educational angle (tutorials, explanations, deep technical analysis)
✓ Timely tech industry news (AI announcements, company decisions, infrastructure failures)
✓ Technical deep dives (Linux boot process, OCR models, system architecture)

RED FLAGS TO AVOID (REJECT IMMEDIATELY):
❌ YouTube Shorts spam: cat videos, ASMR, emoji spam, random hashtags (#ai #shorts #fyp)
❌ Entertainment content: "Who wanna kebab", "cat peed pants", animal videos with emojis
❌ Hashtag spam: Multiple ## hashtags like "#ai #shorts #fyp #trending"
❌ Generic YouTube search results (youtube_search source) - these are usually spam
❌ Low educational value: funny videos, clickbait, sensational titles
❌ Celebrity gossip or drama (unless major tech industry impact)
❌ Product reviews/comparisons (unless deep technical analysis)

DECISION RULE:
If you have to choose between:
- Reddit/HN trend (even if lower momentum) → CHOOSE THIS
- YouTube trend (even if higher momentum) → REJECT (likely spam)

{recent_context.strip()}

{banned_context.strip()}

TRENDING TOPICS TO EVALUATE:
{trends_list}

OUTPUT FORMAT:
Respond with a JSON array containing the indices of your top 10 selected trends, ranked from best to worst.

ENGLISH example response:
{{
  "selected_trends": [5, 12, 3, 18, 7, 22, 1, 15, 9, 20],
  "reasoning": "Selected high-momentum Reddit/HN trends with strong educational value. Prioritized AI tutorials and technical deep dives over YouTube entertainment content."
}}

ITALIAN example response:
{{
  "selected_trends": [5, 12, 3, 18, 7, 22, 1, 15, 9, 20],
  "reasoning": "Selezionati trend da Reddit/HN con alto momentum e forte valore educativo. Priorità data a tutorial AI e analisi tecniche approfondite rispetto a contenuti YouTube di intrattenimento."
}}

IMPORTANT:
- "reasoning" field MUST be in {language_instruction}
- Return ONLY the JSON object, no other text
"""

    return prompt


def parse_llm_curation_response(
    response_text: str,
    original_trends: List[TrendCandidate],
    all_trends: List[TrendCandidate],
    top_n: int = 10
) -> List[TrendCandidate]:
    """
    Parses LLM curation response and returns selected trends.

    Args:
        response_text: Raw LLM response (expected to be JSON)
        original_trends: Original list of trends sent to LLM
        all_trends: All available trends (for replacement if spam filtered)
        top_n: Target number of trends to return

    Returns:
        List of TrendCandidate objects selected by LLM (spam-filtered)

    Raises:
        ValueError: If response cannot be parsed or indices invalid
    """
    try:
        # Clean response text (remove markdown fences if present)
        cleaned_text = response_text.strip()

        # Remove ```json and ``` fences if LLM wrapped response in markdown
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]  # Remove ```json
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]  # Remove ```

        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]  # Remove trailing ```

        cleaned_text = cleaned_text.strip()

        # Parse JSON response
        response_json = json.loads(cleaned_text)

        # Extract selected trend indices
        selected_indices = response_json.get("selected_trends", [])
        reasoning = response_json.get("reasoning", "No reasoning provided")

        if not selected_indices:
            raise ValueError("LLM response missing 'selected_trends' array")

        logger.info(f"LLM curation reasoning: {reasoning}")
        logger.info(f"LLM selected indices: {selected_indices}")

        # Convert indices to trends (indices are 1-based in prompt)
        curated_trends = []
        for idx in selected_indices:
            if idx < 1 or idx > len(original_trends):
                logger.warning(f"Invalid trend index from LLM: {idx} (valid range: 1-{len(original_trends)})")
                continue

            # Convert 1-based index to 0-based
            trend = original_trends[idx - 1]
            logger.info(f"  Index {idx} → '{trend.keyword[:60]}' (source: {trend.source})")
            curated_trends.append(trend)

        logger.info(f"LLM curated {len(curated_trends)} trends from {len(original_trends)} candidates")

        # Post-filter: Remove YouTube spam that LLM incorrectly selected
        # Even with strong prompts, LLMs sometimes select low-quality YouTube content
        pre_filter_count = len(curated_trends)
        curated_trends_filtered = []

        for trend in curated_trends:
            source_lower = trend.source.lower()

            # Keep Reddit and Hacker News (high quality)
            if "reddit" in source_lower or "hackernews" in source_lower:
                curated_trends_filtered.append(trend)
                continue

            # Keep YouTube ONLY if it doesn't look like spam
            if "youtube" in source_lower:
                # Spam indicators: emojis, excessive hashtags, ASMR, funny, shorts tags
                keyword_lower = trend.keyword.lower()
                spam_indicators = [
                    "#shorts", "#fyp", "😂", "😭", "😎", "😳", "😅",
                    "asmr", "#funny", "#ai #", "wanna", "peed", "tortoise", "cat ",
                    "###", "edible slime", "little cat", "found at"
                ]

                is_spam = any(indicator in keyword_lower for indicator in spam_indicators)

                if not is_spam:
                    curated_trends_filtered.append(trend)
                    logger.info(f"  Kept YouTube trend: '{trend.keyword[:60]}' (looks educational)")
                else:
                    logger.warning(f"  REMOVED YouTube spam: '{trend.keyword[:60]}'")

        if len(curated_trends_filtered) < len(curated_trends):
            logger.info(f"Post-filter removed {len(curated_trends) - len(curated_trends_filtered)} YouTube spam trends")

            # Fill remaining slots with top Reddit/HN trends by momentum
            remaining_needed = top_n - len(curated_trends_filtered)
            if remaining_needed > 0:
                # Get all Reddit/HN trends not already selected, sorted by momentum
                reddit_hn_trends = [
                    t for t in all_trends
                    if ("reddit" in t.source.lower() or "hackernews" in t.source.lower())
                    and t not in curated_trends_filtered
                ]
                reddit_hn_sorted = sorted(reddit_hn_trends, key=lambda t: t.momentum_score, reverse=True)

                # Add top N remaining
                for trend in reddit_hn_sorted[:remaining_needed]:
                    curated_trends_filtered.append(trend)
                    logger.info(f"  Added replacement: '{trend.keyword[:60]}' (source: {trend.source})")

        return curated_trends_filtered

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"LLM response was: {response_text[:500]}")
        raise ValueError(f"LLM response is not valid JSON: {e}")
    except Exception as e:
        logger.error(f"Error parsing LLM curation response: {e}")
        raise


def _attempt_curation_improvement(
    original_trends: List[TrendCandidate],
    previous_selection_count: int,
    vertical_id: str,
    memory: Dict,
    llm_generate_fn,
    issue_type: str,
    top_n: int = 10
) -> str:
    """
    Sprint 2: LLM-driven retry mechanism for trend curation.

    When curation returns too few trends (e.g., 1-4 out of 10), this function:
    1. Analyzes why LLM filtering was too aggressive
    2. Generates improved prompt with relaxed criteria
    3. Returns enhanced prompt for retry

    This is NOT a simple fallback - it uses LLM reasoning to understand what went wrong
    and adjust the curation strategy accordingly.

    Args:
        original_trends: Full list of available trends
        previous_selection_count: How many trends were selected in failed attempt
        vertical_id: Content vertical
        memory: Channel memory
        llm_generate_fn: LLM generation function
        issue_type: "too_few" | "too_much_spam" | "parse_fail"
        top_n: Target number of trends (default: 10)

    Returns:
        Improved prompt string for retry curation

    Cost: ~$0.005 per improvement analysis (cheap for recovering failed curation)
    """
    logger.info(f"🔁 Attempting curation improvement for issue: {issue_type}")
    logger.info(f"   Previous selection: {previous_selection_count}/{top_n} trends")

    # Build analysis prompt to understand what went wrong
    analysis_prompt = f"""You are analyzing a failed YouTube trend curation attempt.

CONTEXT:
- Target: Select {top_n} high-quality trends for {vertical_id} channel
- Previous result: Only {previous_selection_count} trends selected (should be {top_n})
- Issue type: {issue_type}

PROBLEM DIAGNOSIS:
The LLM curator was too aggressive in filtering, likely because:
1. TOO STRICT on educational value criteria (rejected borderline-educational trends)
2. TOO STRICT on source quality rules (rejected all YouTube sources even if educational)
3. TOO CONSERVATIVE on brand fit matching
4. OVER-FILTERING spam indicators (rejected trends with minor spam signals)

YOUR TASK:
Provide 2-3 specific improvements to the curation prompt to increase selection without sacrificing quality.

Focus on:
- Relaxing overly strict criteria (e.g., "strongly educational" → "has educational angle")
- Balancing source quality with content value (YouTube CAN be good if educational)
- Being more lenient on minor spam indicators (hashtags alone ≠ spam)
- Prioritizing momentum + timing over perfect brand fit

OUTPUT FORMAT (JSON):
{{
  "improvements": [
    "Specific improvement 1 (e.g., 'Accept YouTube trends if momentum > 0.7 AND keyword includes technical terms')",
    "Specific improvement 2",
    "Specific improvement 3"
  ],
  "reasoning": "Why these improvements will help select more trends without lowering quality"
}}

IMPORTANT: Return ONLY the JSON object, no other text.
"""

    try:
        # Call LLM to analyze failure and suggest improvements
        analysis_response = llm_generate_fn(
            role="curation_optimizer",
            task="Analyze curation failure and suggest prompt improvements",
            context=analysis_prompt,
            style_hints={
                "response_format": "json",
                "max_tokens": 400,
                "temperature": 0.4
            }
        )

        # Parse improvement suggestions
        cleaned_response = analysis_response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        elif cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()

        improvements_json = json.loads(cleaned_response)
        improvements = improvements_json.get("improvements", [])
        reasoning = improvements_json.get("reasoning", "")

        logger.info(f"LLM improvement analysis: {reasoning}")
        for i, improvement in enumerate(improvements, 1):
            logger.info(f"  {i}. {improvement}")

        # Build improved prompt with relaxed criteria
        improved_prompt = build_curation_prompt(
            trends=original_trends,
            vertical_id=vertical_id,
            memory=memory
        )

        # Inject improvements into prompt (replace strict criteria with relaxed version)
        improvement_section = f"""
🔁 RETRY ITERATION - RELAXED CRITERIA:

Previous curation was too strict ({previous_selection_count}/{top_n} selected). Apply these adjustments:
{chr(10).join(f'{i+1}. {imp}' for i, imp in enumerate(improvements))}

UPDATED EVALUATION APPROACH:
- ✓ Accept trends with PARTIAL educational value (not just purely educational)
- ✓ YouTube trends are OK if momentum > 0.6 AND keyword shows technical/educational signals
- ✓ Minor spam indicators (single hashtag, emoji) are acceptable if content has substance
- ✓ Prioritize: MOMENTUM + TIMING > perfect brand fit
- ✓ Goal: Select {top_n} trends that are "good enough" rather than "perfect"

DECISION RULE FOR RETRY:
If trend has:
- High momentum (> 0.6) OR timely relevance
- AND some educational angle (doesn't need to be pure tutorial)
- AND source is Reddit/HN OR YouTube with technical keywords
→ SELECT IT (even if not perfect brand fit)
"""

        # Insert improvement section after "YOUR TASK:" section
        improved_prompt = improved_prompt.replace(
            "YOUR TASK:",
            improvement_section.strip() + "\n\nYOUR TASK:"
        )

        logger.info("✓ Generated improved curation prompt with relaxed criteria")
        return improved_prompt

    except Exception as e:
        logger.error(f"Failed to generate improvement analysis: {e}")
        log_fallback("LLM_CURATION", "GENERIC_IMPROVEMENT", f"LLM analysis failed: {e}", impact="MEDIUM")

        # Fallback: simple relaxation without LLM analysis
        improved_prompt = build_curation_prompt(
            trends=original_trends,
            vertical_id=vertical_id,
            memory=memory
        )

        fallback_improvement = """
🔁 RETRY ITERATION - RELAXED CRITERIA (Fallback):

Previous curation returned too few trends. Apply these relaxed criteria:
1. Accept YouTube trends if momentum > 0.6 AND keyword contains technical terms
2. Minor spam indicators (single hashtag) are OK if content has educational value
3. Prioritize momentum + timing over perfect brand fit
4. Select trends that are "good enough" rather than waiting for "perfect"

Goal: Select at least 7-8 high-quality trends in this retry.
"""

        improved_prompt = improved_prompt.replace(
            "YOUR TASK:",
            fallback_improvement.strip() + "\n\nYOUR TASK:"
        )

        return improved_prompt


def curate_trends_with_llm(
    trends: List[TrendCandidate],
    vertical_id: str,
    memory: Dict,
    llm_generate_fn,
    max_trends_to_evaluate: int = 30,
    top_n: int = 10
) -> List[TrendCandidate]:
    """
    Uses LLM to curate and select the best trends for video creation.

    Phase B.2: Main curation function that integrates LLM evaluation

    Args:
        trends: List of quality-filtered trends (from Phase A)
        vertical_id: Content vertical
        memory: Channel memory
        llm_generate_fn: Function that calls LLM (e.g., llm_router.generate_text)
        max_trends_to_evaluate: How many trends to send to LLM (default: 30)
        top_n: How many trends to return (default: 10)

    Returns:
        List of top N TrendCandidate objects selected by LLM

    Cost Analysis:
        - Input: ~2,000 tokens (30 trends × ~70 tokens each)
        - Output: ~100 tokens (JSON response)
        - Total: ~2,100 tokens × $0.003/1K tokens = $0.006 per curation
        - Very cheap for high-value intelligent filtering!

    Example:
        >>> from yt_autopilot.services.llm_router import generate_text
        >>> curated = curate_trends_with_llm(
        ...     trends=all_trends,
        ...     vertical_id="tech_ai",
        ...     memory=channel_memory,
        ...     llm_generate_fn=generate_text
        ... )
        >>> print(f"LLM selected {len(curated)} top trends")
    """
    if len(trends) <= top_n:
        logger.info(f"Only {len(trends)} trends available, no LLM curation needed")
        return trends

    logger.info(f"Starting LLM curation: {len(trends)} trends → selecting top {top_n}")

    # Build curation prompt
    prompt = build_curation_prompt(
        trends=trends,
        vertical_id=vertical_id,
        memory=memory,
        max_trends_to_evaluate=max_trends_to_evaluate
    )

    logger.debug(f"LLM curation prompt length: {len(prompt)} chars")

    # Call LLM
    try:
        llm_response = llm_generate_fn(
            role="trend_curator",
            task="Select the top 10 trending topics for video creation",
            context=prompt,
            style_hints={
                "response_format": "json",
                "max_tokens": 500,
                "temperature": 0.3  # Low temperature for consistent curation
            }
        )

        logger.info("LLM curation complete, parsing response...")

        # Parse LLM response
        curated_trends = parse_llm_curation_response(
            response_text=llm_response,
            original_trends=trends[:max_trends_to_evaluate],  # LLM only saw top N
            all_trends=trends,  # All available trends for replacement
            top_n=top_n  # Target number of trends
        )

        # Sprint 2: Retry logic with LLM-driven iterative refinement
        # Only retry if selection is severely under target AND we have enough trends
        # Threshold: < 5 trends selected (50% of target) = too aggressive filtering
        if len(curated_trends) < 5 and len(trends) >= 15:
            logger.warning(f"✗ LLM curation severely under-selected ({len(curated_trends)}/{top_n})")
            logger.info("  💡 Attempting LLM-driven curation improvement (1 retry)...")

            try:
                # Call improvement function to get better prompt
                improved_prompt = _attempt_curation_improvement(
                    original_trends=trends,
                    previous_selection_count=len(curated_trends),
                    vertical_id=vertical_id,
                    memory=memory,
                    llm_generate_fn=llm_generate_fn,
                    issue_type="too_few",
                    top_n=top_n
                )

                logger.info("🔁 Re-running LLM curation with improved prompt...")

                # Retry LLM curation with improved prompt
                retry_response = llm_generate_fn(
                    role="trend_curator",
                    task="Select the top 10 trending topics for video creation (retry with relaxed criteria)",
                    context=improved_prompt,
                    style_hints={
                        "response_format": "json",
                        "max_tokens": 500,
                        "temperature": 0.3
                    }
                )

                # Parse retry response
                retry_curated_trends = parse_llm_curation_response(
                    response_text=retry_response,
                    original_trends=trends[:max_trends_to_evaluate],
                    all_trends=trends,
                    top_n=top_n
                )

                # Check if retry improved selection
                logger.info(f"Trend count improvement: {len(curated_trends)} → {len(retry_curated_trends)} (+{len(retry_curated_trends) - len(curated_trends)})")

                if len(retry_curated_trends) >= 7:  # At least 70% of target
                    logger.info("✓ LLM curation IMPROVED after retry! 🎉")
                    curated_trends = retry_curated_trends
                elif len(retry_curated_trends) > len(curated_trends):
                    logger.info(f"✓ Partial improvement ({len(retry_curated_trends)}/{top_n}) - using retry results")
                    curated_trends = retry_curated_trends
                else:
                    logger.warning(f"✗ Retry didn't improve count ({len(retry_curated_trends)}/{top_n})")
                    logger.info("   Using original results + momentum padding")
                    # Keep original curated_trends, will pad below

            except Exception as retry_error:
                logger.error(f"Retry curation failed: {retry_error}")
                log_fallback("LLM_CURATION", "MOMENTUM_PADDING", f"Retry exception: {retry_error}", impact="MEDIUM")
                # Keep original curated_trends, will pad below

        # Final padding if still below target (mechanical fallback after retry)
        if len(curated_trends) < top_n:
            if len(curated_trends) < 5:
                logger.warning(f"LLM returned only {len(curated_trends)} trends after retry, padding to {top_n}")
            else:
                logger.info(f"LLM returned {len(curated_trends)} trends, padding to {top_n}")

            # Add remaining trends by momentum score
            remaining = [t for t in trends if t not in curated_trends]
            remaining_sorted = sorted(remaining, key=lambda t: t.momentum_score, reverse=True)
            curated_trends.extend(remaining_sorted[:top_n - len(curated_trends)])

        # Return exactly top_n trends
        return curated_trends[:top_n]

    except Exception as e:
        logger.error(f"LLM curation failed: {e}")
        log_fallback("LLM_CURATION", "MOMENTUM_ONLY", f"LLM call failed: {e}", impact="HIGH")

        # Fallback: return top N by momentum score
        return sorted(trends, key=lambda t: t.momentum_score, reverse=True)[:top_n]
