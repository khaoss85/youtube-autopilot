"""
Monetization QA Agent: AI-driven YouTube monetization readiness validation.

This agent validates that the complete video package is optimized for
YouTube monetization success, going beyond compliance to ensure the content
can actually generate revenue and engagement.

Key Validation Areas:
1. YouTube Policy Compliance (advertiser-friendly, COPPA, community guidelines)
2. Content-Duration Coherence (does content sustain target duration?)
3. Monetization Potential (watch time optimization, ad placement readiness)
4. Engagement Optimization (retention hooks effectiveness, CTA quality)
5. Narrative Quality (voice consistency, emotional arc, story flow)
6. SEO & Discovery (searchability, metadata optimization)

Complements QualityReviewer (which handles brand safety and basic compliance).
"""

from typing import Dict, Any, Tuple
from yt_autopilot.core.schemas import VideoPlan, VideoScript, VisualPlan, PublishingPackage
from yt_autopilot.services.llm_router import generate_text
from yt_autopilot.core.logger import logger, log_fallback


def validate_monetization_readiness(
    plan: VideoPlan,
    script: VideoScript,
    visuals: VisualPlan,
    publishing: PublishingPackage,
    duration_strategy: Dict[str, Any],
    narrative_arc: Dict[str, Any] = None,
    subscriber_persona: Dict[str, Any] = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    AI-driven validation of YouTube monetization readiness.

    Analyzes the complete video package to ensure it's optimized for:
    - Ad revenue generation (proper duration, ad placement opportunities)
    - Viewer retention (hooks, pacing, emotional engagement)
    - YouTube algorithm favorability (SEO, CTR, watch time signals)
    - Advertiser-friendliness (policy compliance, brand safety)

    Args:
        plan: Video plan with topic and strategy
        script: Video script with voiceover and structure
        visuals: Visual plan with scenes and duration
        publishing: Publishing package with title, description, tags
        duration_strategy: Output from Duration Strategist
        narrative_arc: Optional narrative arc from Narrative Architect
        subscriber_persona: Optional persona of ideal loyal subscriber from workspace config

    Returns:
        Tuple of:
        - approved: bool (True if ready for monetization)
        - message: str (detailed feedback)
        - scores: Dict[str, float] (individual category scores 0-1)

    Example:
        >>> approved, feedback, scores = validate_monetization_readiness(...)
        >>> if approved:
        ...     print("✓ Video is monetization-ready")
        >>> else:
        ...     print(f"Issues: {feedback}")
        ...     print(f"Retention score: {scores['retention_optimization']}")
    """
    logger.info("Monetization QA validating YouTube readiness...")

    # Calculate total duration
    total_duration = sum(scene.est_duration_seconds for scene in visuals.scenes)

    # Extract context
    format_type = duration_strategy.get('format_type', 'unknown')
    target_duration = duration_strategy.get('target_duration_seconds', 0)
    content_depth_score = duration_strategy.get('content_depth_score', 0.5)
    monetization_strategy = duration_strategy.get('monetization_strategy', 'ads')

    # Build narrative context
    narrative_context = ""
    if narrative_arc:
        narrative_context = f"""
NARRATIVE ARC:
- Voice Personality: {narrative_arc.get('voice_personality', 'N/A')}
- Acts: {len(narrative_arc.get('narrative_structure', []))}
- Retention Hooks: {len(narrative_arc.get('retention_hooks', []))}
- Emotional Journey: {narrative_arc.get('emotional_journey', 'N/A')}
"""

    # Build subscriber persona context
    subscriber_context = ""
    evaluation_perspective = "YouTube monetization expert"
    if subscriber_persona:
        why_subscribed = subscriber_persona.get('why_subscribed', 'N/A')
        content_expectations = subscriber_persona.get('content_expectations', {})
        tone_expectation = subscriber_persona.get('tone_expectation', 'N/A')
        value_proposition = subscriber_persona.get('value_proposition', 'N/A')
        avoid_patterns = subscriber_persona.get('avoid_patterns', [])

        subscriber_context = f"""
LOYAL SUBSCRIBER PERSONA (Your Evaluation Perspective):
- Why I Subscribed: {why_subscribed}
- Content Expectations:
  * Depth: {content_expectations.get('depth', 'N/A')}
  * Unique Angle: {content_expectations.get('unique_angle', 'N/A')}
  * Actionability: {content_expectations.get('actionability', 'N/A')}
  * Additional: {', '.join(f'{k}={v}' for k, v in content_expectations.items() if k not in ['depth', 'unique_angle', 'actionability'])}
- Tone I Expect: {tone_expectation}
- Value Proposition: {value_proposition}
- What Would Make Me Unsubscribe: {', '.join(avoid_patterns) if avoid_patterns else 'N/A'}
"""
        evaluation_perspective = f"loyal subscriber who expects: {why_subscribed}"

    # Construct AI validation prompt
    prompt = f"""You are a {evaluation_perspective} validating this video package.

{"" if not subscriber_persona else "IMPORTANT: Evaluate this content from the perspective of an IDEAL LOYAL SUBSCRIBER who has specific expectations for this channel. Your job is to determine if this video will meet those expectations and reinforce subscriber loyalty, while also ensuring monetization success."}

VIDEO PACKAGE ANALYSIS:

TOPIC: "{plan.working_title}"
STRATEGIC ANGLE: {plan.strategic_angle}
TARGET AUDIENCE: {plan.target_audience}

DURATION STRATEGY:
- Format: {format_type} (short <60s / mid 60s-8min / long 8-20min)
- Target Duration: {target_duration}s ({target_duration // 60}min {target_duration % 60}s)
- Actual Duration: {total_duration}s ({total_duration // 60}min {total_duration % 60}s)
- Content Depth Score: {content_depth_score:.2f} (0=thin, 1=deep)
- Monetization Strategy: {monetization_strategy}

SCRIPT:
- Hook: "{script.hook}"
- Content Bullets: {len(script.bullets)} points
- CTA: "{script.outro_cta}"
- Total Voiceover: {len(script.full_voiceover_text)} chars
- Scenes: {len(script.scene_voiceover_map)} mapped
{narrative_context}
{subscriber_context}
PUBLISHING:
- Title: "{publishing.final_title}"
- Description Length: {len(publishing.description)} chars
- Tags: {len(publishing.tags)} tags

VISUAL PLAN:
- Scenes: {len(visuals.scenes)}
- Aspect Ratio: {visuals.aspect_ratio}
- Style: {visuals.video_style_mode}

YOUR TASK:
Validate this video package for YouTube monetization success across 6 categories.
Provide scores (0.0-1.0) and detailed feedback.

VALIDATION CATEGORIES:

1. **YouTube Policy Compliance** (0.0-1.0)
   - Advertiser-friendly content (no controversial topics)
   - COPPA compliance (not made for kids unless specified)
   - Community guidelines (no spam, deceptive practices)
   - Reused content policy (original commentary/value added)

2. **Content-Duration Coherence** (0.0-1.0)
   - Does content depth justify target duration?
   - Is pacing appropriate (not too rushed/padded)?
   - Does Duration Strategist's content_depth_score align with script?
   - Will viewer watch the entire duration?
   {"   - As a loyal subscriber: Does this meet my expected depth level?" if subscriber_persona else ""}

3. **Monetization Potential** (0.0-1.0)
   - Format appropriate for monetization strategy?
     * Short-form (<60s): No ads, only Shorts Fund
     * Mid-form (60s-8min): Pre-roll ads only
     * Long-form (8-20min): Mid-roll ads (max revenue)
   - Duration meets monetization requirements?
   - Ad placement opportunities (natural breaks for mid-roll)?
   - CPM optimization (valuable content for advertisers)?

4. **Engagement Optimization** (0.0-1.0)
   - Hook strength (captures attention in 3 seconds?)
   {"   - As a loyal subscriber: Does this hook deliver what I expect from THIS channel vs competitors?" if subscriber_persona else "   - Emotional engagement (will viewers comment/share?)"}
   - Retention hooks (pattern interrupts, cliffhangers, open loops)
   - CTA effectiveness (specific action, not generic "follow us")
   {"   - As a loyal subscriber: Does this CTA fit my relationship with this channel?" if subscriber_persona else ""}
   - Pacing and energy (maintains interest throughout?)

5. **Narrative Quality** (0.0-1.0)
   - Voice personality consistency (if narrative arc present)
   {"   - As a loyal subscriber: Does this sound like the channel I know and love?" if subscriber_persona else ""}
   - Emotional arc flow (hook → tension → payoff)
   - Story coherence (clear narrative thread)
   - Authenticity (genuine vs templated feel)
   {"   - As a loyal subscriber: Does this feel authentic to why I subscribed?" if subscriber_persona else ""}
   - Punctuation and delivery cues (proper speaking rhythm)

6. **SEO & Discovery** (0.0-1.0)
   - Title optimization (keyword-rich, compelling, under 100 chars)
   - Description quality (searchable, context-rich)
   - Tags relevance (accurate categorization)
   - Thumbnail potential (title suggests visual hook)
   - Searchability (will target audience find this?)

{f'''7. **Subscriber Loyalty Impact** (0.0-1.0) - CRITICAL
   - Does this video reinforce why I subscribed to THIS channel?
   - Will this make me MORE or LESS likely to watch the next video?
   - Does this avoid the patterns that would make me unsubscribe?
   - Brand identity consistency: Does this feel like "my channel"?
   - Series consistency (if applicable): Does this match the series I love?
''' if subscriber_persona else ""}
⚠️ CRITICAL: YOU MUST RESPOND ONLY WITH VALID JSON ⚠️

DO NOT include any text before or after the JSON.
DO NOT use markdown code blocks.
RESPOND WITH RAW JSON ONLY.

RESPOND IN THIS EXACT JSON FORMAT:
{{
  "approved": <true|false>,
  "overall_score": <0.0-1.0, average of all categories>,
  "category_scores": {{
    "policy_compliance": <0.0-1.0>,
    "content_duration_coherence": <0.0-1.0>,
    "monetization_potential": <0.0-1.0>,
    "engagement_optimization": <0.0-1.0>,
    "narrative_quality": <0.0-1.0>,
    "seo_discovery": <0.0-1.0>{', "subscriber_loyalty_impact": <0.0-1.0>' if subscriber_persona else ''}
  }},
  "strengths": [
    "<specific strength 1>",
    "<specific strength 2>",
    "<specific strength 3>"
  ],
  "issues": [
    "<specific issue 1 with recommendation>",
    "<specific issue 2 with recommendation>"
  ],
  "monetization_forecast": {{
    "estimated_cpm_tier": "<low|medium|high|premium>",
    "retention_forecast": "<poor|average|good|excellent>",
    "virality_potential": "<low|medium|high>",
    "revenue_readiness": "<not_ready|basic|optimized|premium>"
  }},
  "recommendation": "<APPROVE|REVISE|REJECT>",
  "feedback_summary": "<2-3 sentences explaining overall verdict>"
}}

APPROVAL CRITERIA:
- APPROVE: overall_score >= 0.75, all category_scores >= 0.6, no critical issues
{f'  * IMPORTANT: subscriber_loyalty_impact MUST be >= 0.65 (higher bar for loyalty)' if subscriber_persona else ''}
- REVISE: overall_score >= 0.5, fixable issues identified
- REJECT: overall_score < 0.5, fundamental problems (wrong format, policy violations)

IMPORTANT:
- Be honest and critical (better to catch issues now than after publishing)
- Focus on MONETIZATION success, not just compliance
- Consider Duration Strategist's reasoning (trust AI decisions if well-justified)
- Provide actionable recommendations for any issues
- RESPOND WITH JSON ONLY, NO OTHER TEXT
"""

    # Call LLM for AI-driven validation
    try:
        response = generate_text(
            role="monetization_qa",
            task=prompt,
            context="",
            style_hints={"response_format": "json", "max_tokens": 1500}
        )

        # Parse JSON response with robust handling
        import json
        import re

        # Try direct JSON parse first
        try:
            validation = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: Extract JSON from markdown code blocks or text
            logger.warning("Direct JSON parse failed, attempting extraction...")

            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                validation = json.loads(json_match.group(1))
                logger.info("Extracted JSON from markdown code block")
            else:
                # Try to find JSON object in text
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
                if json_match:
                    validation = json.loads(json_match.group(0))
                    logger.info("Extracted JSON from text")
                else:
                    raise ValueError("Could not extract valid JSON from response")

        # Extract results
        approved = validation.get('approved', False)
        recommendation = validation.get('recommendation', 'REVISE')
        overall_score = validation.get('overall_score', 0.0)
        category_scores = validation.get('category_scores', {})
        strengths = validation.get('strengths', [])
        issues = validation.get('issues', [])
        forecast = validation.get('monetization_forecast', {})
        feedback_summary = validation.get('feedback_summary', 'No summary provided')

        # Build detailed feedback message
        feedback_lines = [
            f"Monetization QA: {recommendation}",
            f"Overall Score: {overall_score:.2f}/1.00",
            "",
            "Category Scores:"
        ]

        for category, score in category_scores.items():
            status = "✓" if score >= 0.6 else "✗"
            feedback_lines.append(f"  {status} {category.replace('_', ' ').title()}: {score:.2f}")

        if strengths:
            feedback_lines.append("\nStrengths:")
            for strength in strengths:
                feedback_lines.append(f"  ✓ {strength}")

        if issues:
            feedback_lines.append("\nIssues to Address:")
            for issue in issues:
                feedback_lines.append(f"  ✗ {issue}")

        feedback_lines.append("\nMonetization Forecast:")
        feedback_lines.append(f"  CPM Tier: {forecast.get('estimated_cpm_tier', 'unknown')}")
        feedback_lines.append(f"  Retention: {forecast.get('retention_forecast', 'unknown')}")
        feedback_lines.append(f"  Virality: {forecast.get('virality_potential', 'unknown')}")
        feedback_lines.append(f"  Revenue Readiness: {forecast.get('revenue_readiness', 'unknown')}")

        feedback_lines.append(f"\nSummary: {feedback_summary}")

        feedback_message = "\n".join(feedback_lines)

        # Log results
        if approved:
            logger.info(f"✓ Monetization QA APPROVED (score: {overall_score:.2f})")
        else:
            logger.warning(f"✗ Monetization QA {recommendation} (score: {overall_score:.2f})")
            logger.warning(f"  Issues: {len(issues)}")

        # Return results (with overall score included in dict)
        category_scores['overall'] = overall_score
        return approved, feedback_message, category_scores

    except Exception as e:
        logger.error(f"Monetization QA AI validation failed: {e}")
        log_fallback("MONETIZATION_QA", "RULE_BASED", f"LLM validation failed: {e}", impact="HIGH")

        # Fallback: Enhanced validation checks
        issues = []
        warnings = []

        # Check 1: Duration format alignment (CRITICAL)
        if format_type == 'short' and total_duration >= 60:
            issues.append("CRITICAL: Short-form format but duration >= 60s (won't qualify as Short)")
        elif format_type == 'long' and total_duration < 480:
            issues.append("CRITICAL: Long-form monetization but duration < 8min (no mid-roll ads)")

        # Check 2: Duration-visual mismatch (CRITICAL)
        if total_duration < target_duration * 0.7:
            issues.append(f"CRITICAL: Visual duration ({total_duration}s) much shorter than target ({target_duration}s) - needs more scenes")
        elif total_duration > target_duration * 1.3:
            warnings.append(f"Duration ({total_duration}s) exceeds target ({target_duration}s) by >30% - may lose retention")

        # Check 3: Content depth vs duration
        if content_depth_score < 0.3 and total_duration > 180:
            issues.append(f"Low content depth ({content_depth_score:.2f}) doesn't justify {total_duration}s duration - padding risk")
        elif content_depth_score > 0.7 and total_duration < 120:
            warnings.append(f"High content depth ({content_depth_score:.2f}) compressed into {total_duration}s - may feel rushed")

        # Check 4: Hook quality
        if len(script.hook) < 15:
            issues.append("Hook too short (<15 chars) - won't capture attention in first 3s")
        elif len(script.hook) > 200:
            warnings.append("Hook too long (>200 chars) - risk losing viewer")

        # Check 5: CTA generic check
        generic_ctas = ['follow us', 'subscribe', 'like and subscribe', 'smash that button', 'hit the bell']
        if any(generic in script.outro_cta.lower() for generic in generic_ctas):
            warnings.append("CTA is generic - specific action would increase engagement")

        # Check 6: Title length and quality
        if len(publishing.final_title) > 100:
            issues.append("Title exceeds YouTube's 100 char limit - will be truncated")
        elif len(publishing.final_title) < 20:
            warnings.append("Title very short (<20 chars) - may lack context for search")

        # Check 7: Language consistency (basic heuristic)
        # Count italian keywords in title
        italian_keywords = ['tutti', 'cosa', 'come', 'perché', 'nel', 'alla', 'della', 'con']
        english_keywords = ['how', 'what', 'why', 'the', 'this', 'with', 'for']

        title_lower = publishing.final_title.lower()
        has_italian = any(kw in title_lower for kw in italian_keywords)
        has_english = any(kw in title_lower for kw in english_keywords)

        if has_italian and has_english:
            issues.append("Language consistency: Title mixes Italian and English - hurts SEO and discoverability")

        # Check 8: Scene count reasonability
        if len(visuals.scenes) < 3:
            warnings.append(f"Only {len(visuals.scenes)} scenes - may lack visual variety")
        elif len(visuals.scenes) > 20 and total_duration < 300:
            warnings.append(f"{len(visuals.scenes)} scenes in {total_duration}s - very fast cuts may hurt retention")

        # Calculate scores based on issues/warnings
        critical_issues = len([i for i in issues if 'CRITICAL' in i])
        minor_issues = len(issues) - critical_issues

        # Scoring logic
        if critical_issues > 0:
            fallback_score = 0.4  # REJECT territory
        elif minor_issues >= 3:
            fallback_score = 0.6  # REVISE
        elif minor_issues >= 1 or len(warnings) >= 3:
            fallback_score = 0.75  # Borderline APPROVE
        else:
            fallback_score = 0.9  # Strong APPROVE

        fallback_approved = fallback_score >= 0.75 and critical_issues == 0

        # Build detailed fallback message
        fallback_message_lines = [
            f"Monetization QA: {'APPROVE' if fallback_approved else 'REJECT' if critical_issues > 0 else 'REVISE'} (Fallback Mode)",
            f"Overall Score: {fallback_score:.2f}/1.00",
            "",
            "⚠️  NOTE: AI validation unavailable, using enhanced rule-based checks.",
            ""
        ]

        if issues:
            fallback_message_lines.append(f"Issues Found ({len(issues)}):")
            for issue in issues:
                fallback_message_lines.append(f"  ✗ {issue}")
            fallback_message_lines.append("")

        if warnings:
            fallback_message_lines.append(f"Warnings ({len(warnings)}):")
            for warning in warnings:
                fallback_message_lines.append(f"  ⚠️  {warning}")
            fallback_message_lines.append("")

        if not issues and not warnings:
            fallback_message_lines.append("  ✓ All basic checks passed - ready for monetization")

        fallback_message = "\n".join(fallback_message_lines)

        # Calculate category scores based on findings
        scores = {
            'policy_compliance': 0.8,  # Can't check fully without AI
            'content_duration_coherence': max(0.3, 1.0 - (critical_issues * 0.3 + minor_issues * 0.1)),
            'monetization_potential': max(0.3, 1.0 - (critical_issues * 0.4 + minor_issues * 0.15)),
            'engagement_optimization': max(0.5, 1.0 - (len(warnings) * 0.1)),
            'narrative_quality': 0.7,  # Can't evaluate properly without AI
            'seo_discovery': 0.9 if not any('Language consistency' in i for i in issues) else 0.5
        }

        # Add subscriber loyalty score if persona present
        if subscriber_persona:
            scores['subscriber_loyalty_impact'] = 0.7  # Can't evaluate properly without AI

        # Include overall score in dict
        scores['overall'] = fallback_score

        return fallback_approved, fallback_message, scores
