# Monetization QA Retry Loop - Implementation Specification
## AI-Driven Iterative Refinement (Not Fallback!)

**Created**: 2025-11-02
**Priority**: 🔴 HIGH IMPACT (Sprint 1.5)
**Estimated Time**: 2-3 hours (LLM-driven improvement)
**Expected Impact**: +20-30% approval rate

---

## Problem Statement

Currently, when Monetization QA fails (score < 0.75), the package is returned with status `NEEDS_REVISION` but **no automatic retry** is attempted. This blocks ~20-30% of videos that could be easily fixed.

**Example from test**:
```
Monetization QA: REVISE
Overall Score: 0.68/1.00

Issues:
 ✗ Script lacks depth (only 2 bullets for 8min video)
 ✗ No mapped scenes (visual-script sync issue)

→ Package returned as NEEDS_REVISION (no retry)
```

---

## Solution: AI-Driven Iterative Refinement ⭐

**KEY INSIGHT**: This is NOT a simple "fallback" or "try again". This is **intelligent improvement loop** where:

1. **LLM analyzes** Monetization QA feedback with reasoning
2. **LLM generates** targeted improvements (not generic templates!)
3. **System retries** with AI-improved version
4. **Learns** from what works (iterative refinement)

**Philosophy**: Like Quality Reviewer's `_attempt_script_improvement()`, but **LLM-powered** instead of pattern-based!

Add a retry loop that:
1. **Only retries if score is near threshold** (0.60 ≤ score < 0.75)
2. **Applies targeted fixes** based on category scores
3. **Retries Monetization QA once**
4. **Accepts or rejects** based on second attempt

---

## Implementation Steps

### Step 1: Add Helper Function

**Location**: `yt_autopilot/pipeline/build_video_package.py` (before `build_video_package()`)

**Function**: `_attempt_monetization_improvement()`

```python
def _attempt_monetization_improvement(
    script: VideoScript,
    visual_plan: VisualPlan,
    publishing: PublishingPackage,
    video_plan: VideoPlan,
    memory: Dict,
    category_scores: Dict[str, float],
    target_duration: int,
    series_format,
    workspace: Dict,
    duration_strategy: Dict
) -> tuple[VideoScript, VisualPlan, PublishingPackage]:
    """
    Sprint 1.5: Intelligent retry logic for Monetization QA.

    Applies targeted fixes based on category scores:
    - content_depth < 0.70 → Expand script
    - scene_mapping missing → Regenerate visual plan
    - seo_discovery < 0.70 → Regenerate SEO

    Returns:
        Tuple of (improved_script, improved_visual, improved_publishing)
    """
    logger.info("Attempting monetization optimization...")

    improved_script = script
    improved_visual = visual_plan
    improved_publishing = publishing

    # ⭐ LLM-DRIVEN IMPROVEMENT (not pattern-based!)
    # Build improvement prompt with Monetization QA feedback
    improvement_prompt = f"""You are a content optimization expert. Analyze this Monetization QA feedback and improve the video package.

**MONETIZATION QA FEEDBACK:**
{monetization_feedback}

**CATEGORY SCORES:**
{', '.join([f'{k}: {v:.2f}' for k, v in category_scores.items()])}

**CURRENT PACKAGE:**
- Topic: {video_plan.working_title}
- Duration: {target_duration}s
- Script bullets: {len(script.bullets)}
- Current hook: "{script.hook[:100]}..."

**YOUR TASK:**
Analyze the low-scoring categories and generate SPECIFIC improvements:

1. If Content Depth < 0.70:
   - Identify what depth is missing
   - Generate {max(3, int(target_duration/120))} substantive content bullets
   - Ensure bullets add real insight (not generic filler)

2. If Scene Mapping issues:
   - Suggest how to improve visual-script sync
   - Identify narrative beats that need visual emphasis

3. If SEO Discovery < 0.70:
   - Suggest keyword opportunities
   - Recommend title improvements

**CRITICAL**: Be SPECIFIC and ACTIONABLE. No generic advice.

RESPOND WITH JSON:
{{
  "content_improvements": ["bullet 1", "bullet 2", ...],
  "visual_suggestions": "How to improve scene mapping",
  "seo_keywords": ["keyword1", "keyword2", ...],
  "reasoning": "Why these improvements address the QA issues"
}}
"""

    # Call LLM for intelligent improvement analysis
    try:
        from yt_autopilot.services.llm_router import generate_text

        improvement_response = generate_text(
            role="monetization_optimizer",
            task=improvement_prompt,
            context="",
            style_hints={"response_format": "json", "temperature": 0.4}
        )

        # Parse LLM improvement suggestions
        import json, re
        try:
            improvements = json.loads(improvement_response)
        except json.JSONDecodeError:
            # Extract JSON if needed
            json_match = re.search(r'\{[^{}]*"content_improvements"[^{}]*\}', improvement_response, re.DOTALL)
            if json_match:
                improvements = json.loads(json_match.group(0))
            else:
                raise ValueError("Could not parse LLM improvement suggestions")

        # Apply LLM-suggested improvements
        content_improvements = improvements.get('content_improvements', [])
        if content_improvements:
            logger.info(f"  Applying {len(content_improvements)} LLM-suggested content improvements")

            # Merge LLM suggestions with existing bullets
            improved_bullets = script.bullets.copy() + content_improvements

            # Rebuild voiceover with LLM improvements
            improved_voiceover = script.full_voiceover_text + " " + " ".join(content_improvements)

            improved_script = VideoScript(
                hook=script.hook,
                bullets=improved_bullets,
                outro_cta=script.outro_cta,
                full_voiceover_text=improved_voiceover,
                scene_voiceover_map=script.scene_voiceover_map
            )
            logger.info(f"    ✓ Script improved with LLM reasoning")

    except Exception as e:
        logger.warning(f"LLM improvement failed: {e}, using pattern-based fallback")
        # Fallback to simple expansion if LLM fails
        # ... (previous pattern-based code as fallback)

    # Fix 2: Scene Mapping (visual-script sync)
    if not improved_script.scene_voiceover_map or len(improved_script.scene_voiceover_map) == 0:
        logger.info("  Scene mapping missing - regenerating visual plan")

        improved_visual = generate_visual_plan(
            improved_script,
            memory,
            series_format=series_format,
            workspace_config=workspace,
            duration_strategy=duration_strategy
        )
        logger.info("    ✓ Visual plan regenerated")

    # Fix 3: SEO Discovery (keywords/title optimization)
    seo_score = category_scores.get('Seo Discovery', 1.0)
    if seo_score < 0.70:
        logger.info(f"  SEO low ({seo_score:.2f}) - regenerating metadata")

        improved_publishing = generate_publishing_package(video_plan, improved_script)
        logger.info(f"    ✓ SEO regenerated")

    logger.info("Monetization optimization complete")
    return improved_script, improved_visual, improved_publishing
```

---

### Step 2: Modify Pipeline (Monetization QA Section)

**Location**: `yt_autopilot/pipeline/build_video_package.py:1037-1060`

**Current Code** (lines ~1037-1060):
```python
if not monetization_approved:
    logger.warning("✗ Monetization QA FAILED")

    # Return NEEDS_REVISION (no retry)
    return ContentPackage(
        status="NEEDS_REVISION",
        rejection_reason=monetization_feedback,
        ...
    )
```

**New Code with Retry**:
```python
if not monetization_approved:
    overall_score = category_scores.get('overall', 0.0)

    # Retry only if score is near threshold (0.60-0.74)
    if 0.60 <= overall_score < 0.75:
        logger.warning(f"✗ Monetization QA below threshold ({overall_score:.2f})")
        logger.info("  Score is near threshold - attempting optimization (1 retry)")

        # Apply targeted improvements
        try:
            improved_script, improved_visual, improved_publishing = \
                _attempt_monetization_improvement(
                    script=script,
                    visual_plan=visual_plan,
                    publishing=publishing,
                    video_plan=video_plan,
                    memory=memory,
                    category_scores=category_scores,
                    target_duration=duration_strategy['target_duration_seconds'],
                    series_format=series_format,
                    workspace=workspace,
                    duration_strategy=duration_strategy
                )

            # Retry Monetization QA
            logger.info("  Re-running Monetization QA after improvements...")
            retry_approved, retry_feedback, retry_scores = validate_monetization_readiness(
                plan=video_plan,
                script=improved_script,
                visuals=improved_visual,
                publishing=improved_publishing,
                duration_strategy=duration_strategy,
                narrative_arc=narrative_arc
            )

            logger.info(f"Monetization QA retry result: {retry_feedback}")

            if retry_approved:
                logger.info("✓ Monetization QA PASSED after optimization!")
                # Use improved versions
                script = improved_script
                visual_plan = improved_visual
                publishing = improved_publishing
                monetization_approved = True
                monetization_feedback = retry_feedback
                category_scores = retry_scores
            else:
                logger.warning(f"✗ Monetization QA still below threshold after retry")
                logger.warning("  Returning as NEEDS_REVISION")

                # Return improved version even if still not approved
                return ContentPackage(
                    status="NEEDS_REVISION",
                    video_plan=video_plan,
                    script=improved_script,  # Use improved
                    visuals=improved_visual,
                    publishing=improved_publishing,
                    rejection_reason=retry_feedback,
                    llm_raw_script=llm_suggestion,
                    final_script_text=improved_script.full_voiceover_text,
                    editorial_decision=editorial_decision
                )

        except Exception as e:
            logger.error(f"Monetization optimization failed: {e}")
            logger.warning("Falling back to original version")
            # Continue with original (will be returned as NEEDS_REVISION below)

    # Score too low (<0.60) or retry failed → NEEDS_REVISION
    if not monetization_approved:
        logger.warning("✗ Monetization QA FAILED - package needs optimization")

        return ContentPackage(
            status="NEEDS_REVISION",
            rejection_reason=monetization_feedback,
            ...
        )

# If approved (either first attempt or after retry)
logger.info("✓ Monetization QA PASSED - package is monetization-ready")
```

---

## Testing Plan

### Test 1: Score Near Threshold (Should Retry)
```bash
python3 run.py generate --use-llm-curation
```

**Expected**:
- Monetization QA fails with score 0.68
- System logs: "Score is near threshold - attempting optimization"
- Improvements applied (expanded script, regenerated visual)
- Retry Monetization QA
- **Success metric**: Score improves to ≥0.75 OR clear log of retry attempt

### Test 2: Score Too Low (Skip Retry)
Mock a score of 0.50 (very low).

**Expected**:
- Monetization QA fails with score 0.50
- System logs: "Score too low, skipping retry"
- Returns NEEDS_REVISION immediately

### Test 3: Retry Still Fails
Mock improvements that don't raise score enough.

**Expected**:
- First attempt: 0.68
- Retry attempt: 0.72 (still < 0.75)
- Returns NEEDS_REVISION with improved package

---

## Success Metrics

After implementation, measure over 10 test runs:

**Before Sprint 1.5**:
- Videos approved: ~6/10 (60%)
- Videos blocked: ~4/10 (40%)

**After Sprint 1.5** (Expected):
- Videos approved: ~8/10 (80%) ← +20% improvement
- Videos blocked: ~2/10 (20%)
- Retry success rate: ~50% (2 of 4 blocked videos recovered)

---

## Implementation Checklist

- [x] Add `_attempt_monetization_improvement()` function to pipeline ✅ **DONE** (line 201)
- [x] Modify Monetization QA section (Step 8) to add retry logic ✅ **DONE** (line 1259-1364)
- [ ] Test with score 0.68 (near threshold) 🔄 **IN PROGRESS**
- [ ] Test with score 0.50 (too low)
- [ ] Verify retry logs appear in output
- [ ] Measure approval rate improvement (10 test runs)
- [ ] Document actual approval rate gain

**Implementation Date**: 2025-11-02 (Sprint 1.5 completed)

---

## Known Limitations

1. **One retry only** - Prevents infinite loops (deliberate design choice)
2. ~~**Simple content expansion**~~ → **RESOLVED**: Now uses LLM-generated contextual improvements ✅
3. **No cross-agent coordination** - Each fix is independent (could improve in Sprint 2)

## Future Enhancements (Sprint 2)

1. **Multi-step iterative refinement** - Allow 2-3 retry cycles with progressive improvement
2. **Cross-agent learning** - Share successful improvement patterns between Editorial/Duration/Narrative
3. **Retry budget** - Stop after N total retries across pipeline (prevent API cost explosion)
4. **Analytics dashboard** - Track retry success rates per issue type
5. **A/B testing** - Compare LLM vs pattern-based improvements

---

## Why LLM-Driven > Pattern-Based? 🤔

### Pattern-Based (Current Quality Reviewer)
```python
if "hook" in reason:
    improved_hook = "ATTENZIONE: {title} sta esplodendo!"  # Generic template
```

**Pros**: ✅ Fast, ✅ Predictable, ✅ No API cost
**Cons**: ❌ Generic, ❌ Doesn't understand context, ❌ Can't adapt to new issues

### LLM-Driven (Proposed Monetization Retry)
```python
# LLM analyzes feedback and generates contextual improvements
improvement_prompt = f"""Monetization QA says: {feedback}
Generate SPECIFIC improvements for topic: {topic}"""
improvements = llm_generate(improvement_prompt)
```

**Pros**: ✅ Contextual, ✅ Adaptive, ✅ Can reason about trade-offs
**Cons**: ⚠️ API cost (~$0.01 per retry), ⚠️ Slower (2-3s)

**Decision**: Use LLM-driven for Monetization QA because:
1. Higher stakes (revenue optimization)
2. More complex feedback (6 categories, nuanced issues)
3. Cost justified by +20-30% approval rate improvement

---

## Comparison: Quality vs Monetization Retry

| Aspect | Quality Reviewer | Monetization QA |
|--------|-----------------|-----------------|
| **Retry Logic** | ✅ Pattern-based | ⭐ **LLM-driven** |
| **Complexity** | Simple (hook length, etc.) | Complex (6 categories) |
| **Cost** | Free (deterministic) | ~$0.01 per retry |
| **Success Rate** | ~50% (from test logs) | ~60-70% (estimated) |
| **Improvement Quality** | Generic templates | Contextual reasoning |
| **Best For** | Compliance fixes | Monetization optimization |

**Recommendation**: Keep both!
- Quality Reviewer: Pattern-based (fast compliance fixes)
- Monetization QA: LLM-driven (intelligent optimization)

---

## References

- Original plan: `/docs/RETRY_MAPPING_PLAN.md` (this document's parent)
- Test logs: `/tmp/test_e2e_fase2_sprint1.log`
- Related: Quality Reviewer retry (`_attempt_script_improvement` - line 116)
- LLM Router: `yt_autopilot/services/llm_router.py`

---

## Summary: What Makes This "Iterative Refinement"?

1. **Feedback Loop**: QA → Analysis → Improvement → Retry → Learn
2. **AI Reasoning**: LLM understands WHY score is low, not just THAT it's low
3. **Targeted Fixes**: Improvements address specific category issues
4. **Measurable**: Can track improvement delta (0.68 → 0.80)
5. **Learning**: Future: patterns from successful retries inform prompts

This is the foundation for **self-improving content generation** 🚀
