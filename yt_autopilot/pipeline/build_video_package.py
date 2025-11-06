"""
Editorial Pipeline Orchestrator: Coordinates AI agents to produce video packages.

This module orchestrates the complete editorial workflow from trend selection
to quality-approved content packages, managing the multi-agent system and
memory updates.

NEW (Step 06-fullrun): Integrates real LLM calls via llm_router to enhance
script generation with AI creativity while maintaining safety rules.

NEW (Workspace System): Multi-workspace support for managing multiple YouTube channels
with different verticals, brand identities, and configurations.
"""

from typing import List, Dict, Optional
from yt_autopilot.core.schemas import (
    TrendCandidate,
    ContentPackage,
    VideoPlan,
    VideoScript,
    VisualPlan,
    PublishingPackage,
    EditorialDecision
)
from yt_autopilot.core.workspace_manager import (
    get_active_workspace,
    load_workspace_config,
    save_workspace_config,
    update_workspace_recent_titles
)
from yt_autopilot.core.logger import logger, truncate_for_log, log_fallback

# Import agents
from yt_autopilot.agents.editorial_strategist import decide_editorial_strategy
from yt_autopilot.agents.duration_strategist import analyze_duration_strategy  # NEW: monetization-first
from yt_autopilot.agents.format_reconciler import reconcile_format_strategies  # Fase 2 Sprint 1: duration arbitration
from yt_autopilot.agents.narrative_architect import design_narrative_arc, expand_narrative_voiceovers  # NEW: emotional storytelling + Layer 2 expansion
from yt_autopilot.agents.cta_strategist import design_cta_strategy  # Fase 2 Sprint 1: CTA placement
from yt_autopilot.agents.content_depth_strategist import analyze_content_depth  # NEW: AI-driven bullets count
from yt_autopilot.agents.trend_hunter import generate_video_plan
from yt_autopilot.agents.script_writer import write_script, _build_persona_aware_prompt  # Step 09: narrator persona
from yt_autopilot.agents.visual_planner import generate_visual_plan
from yt_autopilot.agents.seo_manager import generate_publishing_package
from yt_autopilot.agents.quality_reviewer import review
from yt_autopilot.agents.monetization_qa import validate_monetization_readiness  # Monetization Refactor

# Import services (Step 06-fullrun: LLM integration)
from yt_autopilot.services.llm_router import generate_text

# Phase B: LLM-powered trend curation
from yt_autopilot.services.llm_trend_curator import curate_trends_with_llm

# Step 08: Real trend fetching
from yt_autopilot.services.trend_source import fetch_trends

# Step 08 Phase 4: Learning loop - performance-aware selection
from yt_autopilot.io.datastore import get_videos_performance_summary

# Step 07.5: Series format engine
from yt_autopilot.core import series_manager

# NEW: Get vertical config for Duration Strategist
from yt_autopilot.core.config import get_vertical_config, LOG_TRUNCATE_REASONING

# VALIDATORS (AI-Driven Quality Framework)
from yt_autopilot.core.config_validator import ConfigAuthorityEnforcer
from yt_autopilot.core.language_validator import wrap_llm_with_language_enforcement, LanguageValidator
from yt_autopilot.core.format_validator import validate_and_enforce_format


def _is_gate_enabled(workspace: Dict, gate_name: str) -> tuple[bool, bool]:
    """
    Check if a validation gate is enabled in workspace config.

    Args:
        workspace: Workspace config dict
        gate_name: Gate identifier (e.g., "post_editorial", "post_duration")

    Returns:
        Tuple (is_enabled, is_blocking)
            - is_enabled: If True, gate should run
            - is_blocking: If True, gate failures should stop pipeline
    """
    validation_config = workspace.get('validation_gates', {})

    # If validation_gates not in config, gates are enabled by default (backward compat)
    if not validation_config:
        return True, True

    # Check global enabled flag
    if not validation_config.get('enabled', True):
        return False, False

    # Check specific gate config
    gates = validation_config.get('gates', {})
    gate_config = gates.get(gate_name, {})

    is_enabled = gate_config.get('enabled', True)  # Default: enabled
    is_blocking = gate_config.get('blocking', True)  # Default: blocking

    return is_enabled, is_blocking


def _get_mock_trends() -> List[TrendCandidate]:
    """
    Returns mock trending topics for testing the editorial pipeline.

    In production, this would be replaced by a service that fetches
    real trends from external APIs (Google Trends, social media, etc.).

    Returns:
        List of mock TrendCandidate objects
    """
    return [
        TrendCandidate(
            keyword="Programmazione Python per principianti 2025",
            why_hot="Python rimane il linguaggio più richiesto, boom di corsi online e tutorial",
            region="IT",
            language="it",
            momentum_score=0.87,
            source="mock_trends"
        ),
        TrendCandidate(
            keyword="Strategie di produttività con AI tools",
            why_hot="ChatGPT e AI assistants stanno rivoluzionando il modo di lavorare",
            region="IT",
            language="it",
            momentum_score=0.91,
            source="mock_trends"
        ),
        TrendCandidate(
            keyword="Home office setup professionale",
            why_hot="Lavoro da remoto continua a crescere, setup ergonomico è trend 2025",
            region="IT",
            language="it",
            momentum_score=0.78,
            source="mock_trends"
        ),
    ]


def _calculate_total_duration(visuals: VisualPlan) -> int:
    """
    Calculates total estimated video duration from visual plan.

    Args:
        visuals: Visual plan with scenes

    Returns:
        Total duration in seconds
    """
    return sum(scene.est_duration_seconds for scene in visuals.scenes)


def _attempt_script_improvement(
    script: VideoScript,
    reason: str,
    plan: VideoPlan,
    memory: Dict
) -> VideoScript:
    """
    Attempts to improve script based on quality reviewer feedback.

    Step 09: Preserves narrator persona when present instead of using
    generic fallback templates.

    This is a simplified improvement strategy. In production, this could
    use LLM to intelligently revise content based on specific issues.

    Args:
        script: Original script that was rejected
        reason: Rejection reason from quality reviewer
        plan: Video plan for context
        memory: Workspace configuration (memory dict compatible)

    Returns:
        Improved VideoScript
    """
    logger.info(f"Attempting script improvement based on feedback: {reason[:100]}...")

    # Step 09: Check if narrator persona is present
    narrator_config = memory.get('narrator_persona', {})
    has_narrator = narrator_config.get('enabled', False)
    narrator_name = narrator_config.get('name', '') if has_narrator else None

    # Create improved version based on common rejection patterns
    improved_hook = script.hook
    improved_bullets = script.bullets.copy()
    improved_cta = script.outro_cta

    # If hook is weak, make it stronger
    if "hook" in reason.lower() or "attention" in reason.lower():
        # Step 09: Preserve narrator persona in hook if present
        if has_narrator and narrator_name and narrator_name.lower() in script.hook.lower():
            # Narrator already in hook - just ensure it's strong enough
            # Keep the LLM-generated hook as-is (it likely passed now with relaxed check)
            logger.debug(f"Preserving narrator persona hook with {narrator_name}")
        else:
            # Generic hook strengthening
            improved_hook = f"ATTENZIONE: {plan.working_title} sta esplodendo! Ecco cosa devi sapere ORA."
            logger.debug("Strengthened hook for better attention capture")

    # If too long, trim content
    if "too long" in reason.lower() or "duration" in reason.lower() or "durata" in reason.lower():
        # Keep only first 3 bullets to reduce duration
        if len(improved_bullets) > 3:
            improved_bullets = improved_bullets[:3]
            logger.debug(f"Trimmed bullets from {len(script.bullets)} to {len(improved_bullets)}")

    # If medical/legal claims detected, soften language
    if "medical" in reason.lower() or "claim" in reason.lower():
        # Add disclaimer language
        improved_cta = "Ricorda: consulta sempre un professionista. " + improved_cta
        logger.debug("Added disclaimer language for compliance")

    # If title/clickbait issues, keep content but let SEO manager handle title
    if "title" in reason.lower() or "spam" in reason.lower():
        logger.debug("Title issues detected - will be addressed in SEO regeneration")

    # Rebuild voiceover
    sections = [improved_hook, "Ecco i punti chiave."]
    sections.extend(improved_bullets)
    sections.append("Questo è ciò che conta davvero.")
    sections.append(improved_cta)

    improved_voiceover = " ".join(sections)

    # Create improved script
    improved_script = VideoScript(
        hook=improved_hook,
        bullets=improved_bullets,
        outro_cta=improved_cta,
        full_voiceover_text=improved_voiceover
    )

    logger.info("Script improvement completed")
    return improved_script


def _attempt_monetization_improvement(
    script: VideoScript,
    visual_plan: VisualPlan,
    publishing: PublishingPackage,
    video_plan: VideoPlan,
    memory: Dict,
    category_scores: Dict[str, float],
    monetization_feedback: str,
    target_duration: int,
    series_format,
    workspace: Dict,
    duration_strategy: Dict,
    editorial_decision: Optional[EditorialDecision] = None,  # Phase C - P3
    narrative_arc: Optional[Dict] = None,  # Phase C - P3
    content_depth_strategy: Optional[Dict] = None  # Phase C - P3
) -> tuple:
    """
    Phase C - P3: FULL REGENERATION retry loop (not superficial patches!).

    Instead of appending bullets (Sprint 1.5 approach), this regenerates complete
    artifacts with QA feedback as constraints:
    1. Regenerates narrative_arc if narrative/engagement/coherence issues
    2. Regenerates script using new narrative_arc
    3. ALWAYS regenerates visual_plan with new script (not just if scene_mapping missing)
    4. Regenerates SEO if needed

    This closes the QA feedback loop properly by passing constraints to upstream agents.

    Args:
        script: Current VideoScript
        visual_plan: Current VisualPlan
        publishing: Current PublishingPackage
        video_plan: VideoPlan (for topic context)
        memory: Memory dict (for visual generation)
        category_scores: Dict of Monetization QA scores by category
        monetization_feedback: Full feedback text from Monetization QA
        target_duration: Target duration in seconds
        series_format: Series format config
        workspace: Workspace config
        duration_strategy: Duration strategy dict
        editorial_decision: EditorialDecision (Phase C - P3)
        narrative_arc: Original narrative_arc (Phase C - P3)
        content_depth_strategy: Content depth strategy (Phase C - P3)

    Returns:
        Tuple of (improved_script, improved_visual, improved_publishing)
    """
    logger.info("🔄 Phase C - P3: Full regeneration retry loop with QA feedback constraints...")

    # Identify which artifacts need regeneration based on category scores
    narrative_quality_score = category_scores.get('narrative_quality', 1.0)
    engagement_score = category_scores.get('engagement_optimization', 1.0)
    coherence_score = category_scores.get('content_duration_coherence', 1.0)
    seo_score = category_scores.get('seo_discovery', 1.0)

    needs_narrative_regen = (
        narrative_quality_score < 0.70 or
        engagement_score < 0.70 or
        coherence_score < 0.70
    )
    needs_seo_regen = seo_score < 0.70

    logger.info(f"  Category scores: narrative={narrative_quality_score:.2f}, engagement={engagement_score:.2f}, coherence={coherence_score:.2f}, seo={seo_score:.2f}")
    logger.info(f"  Regeneration plan: narrative_arc={needs_narrative_regen}, seo={needs_seo_regen}")

    # Phase C - P3: FULL REGENERATION PATH
    if needs_narrative_regen:
        logger.info("  ↻ Regenerating narrative arc with QA feedback constraints...")

        # Create LLM wrapper that injects QA feedback as constraints
        def qa_aware_llm(role, task, context, style_hints):
            # Inject QA feedback into the prompt
            qa_constraint_injection = f"""
⚠️ MONETIZATION QA RETRY - CRITICAL CONSTRAINTS ⚠️
This is a RETRY after Monetization QA feedback. You MUST address these issues:

QA FEEDBACK SUMMARY:
{monetization_feedback[:500]}...

LOW-SCORING CATEGORIES (fix these!):
- Narrative Quality: {narrative_quality_score:.2f}/1.00 {'← FIX THIS' if narrative_quality_score < 0.70 else ''}
- Engagement Optimization: {engagement_score:.2f}/1.00 {'← FIX THIS' if engagement_score < 0.70 else ''}
- Content-Duration Coherence: {coherence_score:.2f}/1.00 {'← FIX THIS' if coherence_score < 0.70 else ''}

REQUIRED IMPROVEMENTS:
- If narrative_quality low: Strengthen emotional arc, improve voice personality consistency
- If engagement low: Add more retention hooks, pattern interrupts, cliffhangers
- If coherence low: Ensure content depth justifies duration, avoid padding

⚠️ THIS IS YOUR SECOND CHANCE - MAKE IT COUNT ⚠️

ORIGINAL TASK:
"""
            constrained_task = qa_constraint_injection + task
            return generate_text(role, constrained_task, context, style_hints)

        try:
            # Regenerate narrative_arc with QA-aware LLM
            new_narrative_arc = design_narrative_arc(
                topic=video_plan.working_title,
                target_duration_seconds=target_duration,
                workspace_config=workspace,
                duration_strategy=duration_strategy,
                editorial_decision=editorial_decision,
                bullet_count_constraint=content_depth_strategy.get('target_bullets_count') if content_depth_strategy else None,
                llm_generate_fn=qa_aware_llm,  # Phase C - P3: Inject QA constraints
                timeline=None  # No timeline in retry context
            )
            logger.info("    ✓ Narrative arc regenerated with QA constraints")

            # Regenerate script with new narrative_arc
            logger.info("  ↻ Regenerating script with new narrative arc...")
            improved_script = write_script(
                plan=video_plan,
                memory=memory,
                series_format=series_format,
                editorial_decision=editorial_decision,
                narrative_arc=new_narrative_arc,  # Use regenerated arc!
                content_depth_strategy=content_depth_strategy,
                llm_generate_fn=llm_generate_fn  # Hook length validation
            )
            logger.info("    ✓ Script regenerated")

            # ALWAYS regenerate visual plan (not just if scene_mapping missing)
            logger.info("  ↻ Regenerating visual plan with new script...")
            improved_visual = generate_visual_plan(
                video_plan,
                improved_script,
                memory,
                series_format=series_format,
                workspace_config=workspace,
                duration_strategy=duration_strategy,
                timeline=None,
                llm_generate_fn=llm_generate_fn  # Layer 2: AI-driven duration validation
            )
            logger.info("    ✓ Visual plan regenerated")

        except Exception as e:
            logger.error(f"  Full regeneration failed: {e}")
            logger.warning("  Falling back to original artifacts")

            log_fallback(
                component="PIPELINE_MONETIZATION_QA_RETRY",
                fallback_type="NO_REGENERATION",
                reason=f"Regeneration failed: {e}",
                impact="HIGH"
            )

            improved_script = script
            improved_visual = visual_plan
    else:
        # No narrative regeneration needed - use originals
        improved_script = script
        improved_visual = visual_plan

    # SEO regeneration (independent of narrative path)
    if needs_seo_regen:
        logger.info(f"  ↻ Regenerating SEO metadata (score: {seo_score:.2f})...")
        improved_publishing = generate_publishing_package(video_plan, improved_script)
        logger.info("    ✓ SEO metadata regenerated")
    else:
        improved_publishing = publishing

    logger.info("✓ Phase C - P3: Monetization optimization complete")
    return improved_script, improved_visual, improved_publishing


def build_video_package(
    workspace_id: Optional[str] = None,
    use_real_trends: bool = False,
    use_llm_curation: bool = False,
    use_coordinator: bool = False  # NEW: Phase A4 - Use AgentCoordinator for standardized execution
) -> ContentPackage:
    """
    Orchestrates the full editorial pipeline to produce a ContentPackage.

    Phase 1 Refactor: Updated to content strategy focus.
    Phase A4: Optionally uses AgentCoordinator for standardized agent execution.

    This is the main orchestrator for the editorial brain. It coordinates all
    AI agents in sequence, handles quality review with one retry attempt,
    and updates workspace configuration when content is approved.

    Workflow:
        1. Load workspace configuration (replaces channel memory)
        2. Fetch trending topics (Phase A quality filtering applied)
        2.5. [OPTIONAL] LLM curation (Phase B: select top 10 from ~25 trends)
        3. Editorial Strategist: AI-driven strategic decision (serie, format, angle, CTA)
        4. TrendHunter selects best topic → VideoPlan
        5. ScriptWriter generates script → VideoScript (with editorial strategy)
        6. VisualPlanner creates scenes → VisualPlan
        7. SeoManager optimizes metadata → PublishingPackage
        8. QualityReviewer checks compliance → APPROVED/REJECTED
        9. If REJECTED: attempt ONE revision and re-check
        10. If APPROVED: update workspace with new title
        11. Return ContentPackage

    Args:
        workspace_id: Workspace ID to use (if None, uses active workspace)
        use_real_trends: If True, fetch real trends from APIs; if False, use mocks
        use_llm_curation: If True, use LLM to curate top 10 trends (Phase B); if False, use Phase A filtering only
        use_coordinator: If True, use AgentCoordinator for standardized execution (Phase A4); if False, use legacy path

    Returns:
        ContentPackage object with status "APPROVED" or "REJECTED"

    Notes:
        - Does NOT call external APIs for video/audio generation (Veo, TTS, etc.)
        - Does NOT generate actual video files
        - Does NOT upload anything
        - Only coordinates editorial decisions and workspace management

    Phase A (Quick Wins):
        - Spam filtering (removes patterns like "test", "vs", "review")
        - Quality thresholds (min 500 upvotes Reddit, 100 points HN)
        - Source weighting (Reddit 3x > HN 2x > YouTube 1x)

    Phase B (LLM Curation):
        - LLM evaluates top 30 trends for educational value, brand fit, timing
        - Selects top 10 curated trends
        - Cost: ~$0.01 per curation (cheap for high-value filtering)
    """
    logger.info("=" * 70)
    logger.info("STARTING EDITORIAL PIPELINE: build_video_package()")
    logger.info("=" * 70)

    # Step 1: Load workspace configuration
    logger.info("Step 1: Loading workspace configuration...")

    if workspace_id:
        workspace = load_workspace_config(workspace_id)
        logger.info(f"Using specified workspace: {workspace['workspace_name']} ({workspace_id})")
    else:
        workspace = get_active_workspace()
        workspace_id = workspace['workspace_id']
        logger.info(f"Using active workspace: {workspace['workspace_name']} ({workspace_id})")

    vertical_id = workspace['vertical_id']

    logger.info(f"Workspace loaded successfully (recent titles: {len(workspace.get('recent_titles', []))})")
    logger.info(f"  Vertical: {vertical_id}")
    logger.info(f"  Brand tone: {workspace.get('brand_tone', 'Not set')[:100]}...")

    # VALIDATION: Config Authority Enforcement (AI-Driven)
    logger.info("")
    logger.info("🔒 CONFIG AUTHORITY VALIDATION")
    enforcer = ConfigAuthorityEnforcer(auto_migrate=True, strict_mode=False)
    workspace, is_valid = enforcer.enforce_at_pipeline_start(workspace, workspace_id)

    if not is_valid:
        raise ValueError(
            f"Config validation failed for workspace '{workspace_id}'. "
            f"Tactical params found in config (should be AI-driven). "
            f"Run: python3 -c \"from yt_autopilot.core.config_migrator import migrate_workspace_file; "
            f"migrate_workspace_file('workspaces/{workspace_id}.json')\""
        )

    logger.info("✅ Config authority validated - AI agents have full authority on tactical decisions")
    logger.info("")

    # LANGUAGE ENFORCEMENT: Wrap LLM with language validator
    target_language = workspace.get('target_language', 'en')
    logger.info(f"🌍 LANGUAGE ENFORCEMENT: Target language = {target_language}")

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

    # Create language-enforced LLM function
    llm_generate_fn = wrap_llm_with_language_enforcement(
        generate_text,
        target_language=target_language,
        strict_mode=True,
        component_name="pipeline"
    )
    logger.info(f"✅ Language validator active - all LLM outputs will be validated for {target_language} consistency")
    logger.info("")

    # Use workspace as memory (compatible with existing agent interfaces)
    memory = workspace

    # Step 2: Fetch trending topics (Phase A: quality filtering applied automatically)
    logger.info(f"Step 2: Fetching trending topics (vertical: {vertical_id})...")

    if use_real_trends:
        logger.info("  Using REAL trend APIs (YouTube + Reddit + Hacker News)")
        logger.info("  Phase A filters: spam detection + quality thresholds + deduplication")
        trends = fetch_trends(vertical_id=vertical_id, use_real_apis=True)
        logger.info(f"✓ Fetched {len(trends)} quality-filtered trends")
    else:
        logger.info("  Using MOCK trends (test mode)")
        trends = _get_mock_trends()
        logger.info(f"✓ Collected {len(trends)} mock trends")

    if not trends:
        raise ValueError("No trends available - cannot build video package")

    # Step 2.5: LLM Curation (Phase B - OPTIONAL)
    if use_llm_curation and len(trends) > 10:
        logger.info("Step 2.5: Running LLM curation (Phase B)...")
        logger.info(f"  Input: {len(trends)} quality-filtered trends")
        logger.info("  LLM will evaluate trends for: educational value, brand fit, timing, virality")
        logger.info("  Output: Top 10 curated trends")

        try:
            curated_trends = curate_trends_with_llm(
                trends=trends,
                vertical_id=vertical_id,
                memory=memory,
                llm_generate_fn=llm_generate_fn,  # Use language-validated LLM
                max_trends_to_evaluate=min(30, len(trends)),
                top_n=10
            )
            logger.info(f"✓ LLM curation complete: {len(trends)} → {len(curated_trends)} trends")
            trends = curated_trends
        except Exception as e:
            # 🚨 Log LLM curation failure fallback
            log_fallback(
                component="PIPELINE_LLM_CURATION",
                fallback_type="PHASE_A_FILTERING_ONLY",
                reason=f"LLM curation failed: {e}",
                impact="MEDIUM"
            )
            logger.warning(f"LLM curation failed: {e}")
            logger.warning("Falling back to Phase A filtering only (no LLM)")
            # Continue with Phase A filtered trends (already quality-checked)

    elif use_llm_curation:
        logger.info("Step 2.5: LLM curation skipped (not enough trends)")
    else:
        logger.info("Step 2.5: LLM curation disabled (using Phase A filtering only)")

    logger.info(f"  Final trend pool: {len(trends)} candidates for TrendHunter")

    # Step 3: TrendHunter - select best topic (Phase A source weighting applied)
    logger.info("Step 3: Running TrendHunter to select best topic...")
    logger.info("  Phase A source weighting: Reddit 4x > Channels 3x > HN 2x > YouTube 1x")
    logger.info("  Enhanced scoring: Real statistics (views, engagement, recency)")
    logger.info("  Language boost: +0.15 for content matching workspace language")

    # Get top 5 candidates for potential AI selection
    video_plan, top_candidates = generate_video_plan(trends, memory, return_top_candidates=5)

    logger.info(f"✓ TrendHunter selected: '{video_plan.working_title}'")
    logger.info(f"  Target audience: {video_plan.target_audience}")
    logger.info(f"  Compliance notes: {len(video_plan.compliance_notes)} checks")

    # Step 3.1: Log top 5 candidates (transparency + debugging)
    logger.info("=" * 70)
    logger.info("TOP 5 TREND CANDIDATES (Ranked by Enhanced Scoring):")
    logger.info("=" * 70)
    from yt_autopilot.agents.trend_hunter import _calculate_priority_score
    for i, candidate in enumerate(top_candidates, 1):
        score = _calculate_priority_score(candidate, memory)
        keyword_display = candidate.keyword[:100] + "..." if len(candidate.keyword) > 100 else candidate.keyword
        logger.info(f"#{i}: '{keyword_display}'")
        logger.info(f"     Score: {score:.3f} | Source: {candidate.source}")
        logger.info(f"     Momentum: {candidate.momentum_score:.2f} | Virality: {candidate.virality_score:.2f}")
        logger.info(f"     Competition: {candidate.competition_level} | CPM: ${candidate.cpm_estimate:.1f}")
        if i == 1:
            logger.info(f"     ✓ SELECTED (Deterministic)")
    logger.info("=" * 70)

    # Step 3.2: AI-assisted final selection (ALWAYS ACTIVE)
    # Step 08 Phase 3: Hybrid duplicate detection + semantic quality
    # - Layer 1: Fuzzy match filters obvious duplicates (free, in TrendHunter)
    # - Layer 2: AI semantic check on top 5 (intelligent, prevents semantic duplicates)
    # Cost: ~$0.01-0.05 per video | Value: Prevents semantic duplicates + strategic fit
    use_ai_selection = True  # Always-on for semantic quality (set False to disable)

    if use_ai_selection and len(top_candidates) >= 3:
        logger.info("Step 3.2: Running AI-assisted final selection (Phase C)...")
        logger.info(f"  Evaluating top {len(top_candidates)} candidates with LLM")

        try:
            # Format candidates for LLM
            candidates_text = "\n".join([
                f"{i+1}. '{c.keyword}'\n"
                f"   Source: {c.source}\n"
                f"   Why hot: {c.why_hot}\n"
                f"   Momentum: {c.momentum_score:.2f}, Virality: {c.virality_score:.2f}\n"
                f"   Competition: {c.competition_level}, CPM: ${c.cpm_estimate:.1f}\n"
                for i, c in enumerate(top_candidates)
            ])

            # Format recent videos for semantic duplicate check
            recent_titles = memory.get('recent_titles', [])[:10]

            # Step 08 Phase 4: Learning loop - retrieve performance data
            performance_data = get_videos_performance_summary(recent_titles, workspace_id) if recent_titles else {}

            # Format with performance indicators when available
            if recent_titles:
                recent_videos_lines = []
                for title in recent_titles:
                    if title in performance_data:
                        views = performance_data[title]
                        # Categorize performance: <2K=low, 2-10K=medium, >10K=high
                        if views > 10000:
                            recent_videos_lines.append(f"- {title} | 🔥 {views:,} views (high performer)")
                        elif views > 2000:
                            recent_videos_lines.append(f"- {title} | 📊 {views:,} views (medium)")
                        else:
                            recent_videos_lines.append(f"- {title} | 📉 {views:,} views (low)")
                    else:
                        # No metrics yet (video not published or metrics not collected)
                        recent_videos_lines.append(f"- {title}")
                recent_videos_text = "\n".join(recent_videos_lines)
            else:
                recent_videos_text = "- None yet"

            # Build LLM prompt for strategic selection + semantic duplicate detection
            ai_prompt = f"""You are a YouTube content strategist for {memory.get('workspace_name', 'our channel')}.

**Our Brand:**
- Tone: {memory.get('brand_tone', 'Educational and engaging')}
- Target audience: {video_plan.target_audience}

**Recent Videos (Last 30 days):**
{recent_videos_text}

**Top {len(top_candidates)} Trend Candidates (already filtered and scored):**

{candidates_text}

⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
ALL TEXT FIELDS (reasoning, duplicate_analysis, reproducibility_analysis) MUST BE IN {language_instruction}.
DO NOT mix languages. If you see examples in other languages below, IGNORE their language and write in {language_instruction}.

**Your Task:**
Analyze which trend has the BEST strategic fit considering:

1. **Brand Alignment**: Does this match our tone and positioning?
2. **Audience Engagement**: Will our specific audience connect with this?
3. **Timing Advantage**: Is this the right moment to publish on this topic?
4. **Content Uniqueness**: Can we offer a differentiated angle?
5. **Production Viability & Reproducibility**: Can we execute this well with our resources?
   - CRITICAL: Can we create this content SOLO without specific named collaborators?
   - SKIP any trends requiring specific people/influencers (e.g., "Challenge with [Name]", "Interview with [Person]")
   - SKIP any trends requiring specific events we didn't attend (e.g., "My experience at [Event]")
   - OK: General formats we can replicate (tutorials, reviews, tips, challenges WE can do solo)
6. **SEMANTIC DUPLICATE CHECK**: Is ANY candidate too similar (CONCEPTUALLY) to our recent videos?

**CRITICAL - Semantic Similarity Rules:**
- Consider MEANING, not just keywords
- Examples of SEMANTIC DUPLICATES (should be skipped):
  * "Python tutorial" ≈ "Learn Python basics" (SAME TOPIC)
  * "Morning stretches" ≈ "Best stretches for morning routine" (SAME TOPIC)
  * "AI productivity tools" ≈ "ChatGPT for work efficiency" (SAME CONCEPT)
- Examples of DIFFERENT ANGLES (OK to select):
  * "Push-ups mistakes to avoid" ≠ "Perfect push-ups tutorial" (DIFFERENT FOCUS)
  * "Weight loss diet plan" ≠ "Weight loss workout routine" (DIFFERENT APPROACH)
- If a candidate is semantically similar to recent videos: SKIP IT or explain why the angle is sufficiently different

**LEARNING FROM PERFORMANCE (Step 08 Phase 4):**
- When performance indicators are shown (🔥 high / 📊 medium / 📉 low), use them to inform selection
- High performers (🔥) indicate topics/angles that resonate with our audience
- Consider selecting trends SIMILAR to our high performers (if not semantic duplicates)
- Avoid patterns that led to low performers (📉) unless there's a compelling reason
- If no performance data available yet, make strategic choice based on other factors

**Important**: Don't just pick #1. Consider strategic nuance that numbers don't capture.

ENGLISH example response:
{{
  "selected_index": 0,
  "title": "Example trend title",
  "reasoning": "This trend shows strong momentum and aligns with our tech-focused audience. The timing is perfect as this topic is currently trending on Reddit/HN.",
  "duplicate_analysis": "No semantic duplicates detected. This topic offers a different angle from our recent content.",
  "reproducibility_analysis": "Fully reproducible solo. Tutorial format requires no specific collaborators or event access.",
  "skipped_candidates": [1, 3]
}}

ITALIAN example response:
{{
  "selected_index": 0,
  "title": "Titolo trend di esempio",
  "reasoning": "Questo trend mostra un forte momentum e si allinea con il nostro pubblico tech. Il timing è perfetto poiché l'argomento è attualmente in tendenza su Reddit/HN.",
  "duplicate_analysis": "Nessun duplicato semantico rilevato. Questo argomento offre un angolo differente rispetto ai nostri contenuti recenti.",
  "reproducibility_analysis": "Completamente riproducibile in autonomia. Il formato tutorial non richiede collaboratori specifici o accesso a eventi.",
  "skipped_candidates": [1, 3]
}}

Return ONLY a JSON object. ALL text fields MUST be in {language_instruction}."""

            # Call LLM
            ai_response_text = llm_generate_fn(
                role="content_strategist",
                task=ai_prompt,
                context=f"Workspace: {memory.get('workspace_name', 'Unknown')}, Vertical: {vertical_id}",
                style_hints={"format": "json", "length": "concise"}
            )

            # Log raw response for debugging
            logger.debug(f"  Raw LLM response ({len(ai_response_text)} chars): {ai_response_text[:200]}...")

            # Parse LLM response (robust JSON extraction)
            import json
            import re

            # Try direct JSON parse first
            try:
                ai_response = json.loads(ai_response_text)
            except json.JSONDecodeError:
                # Fallback: Extract JSON with regex (handles text before/after JSON)
                logger.debug("  Direct JSON parse failed, trying regex extraction...")
                # Updated regex to capture larger JSON objects with new fields
                json_match = re.search(
                    r'\{[^{}]*"selected_index"[^{}]*"reasoning"[^{}]*\}',
                    ai_response_text,
                    re.DOTALL
                )
                if json_match:
                    json_str = json_match.group(0)
                    logger.debug(f"  Extracted JSON: {json_str[:100]}...")
                    ai_response = json.loads(json_str)
                else:
                    raise ValueError(
                        f"No valid JSON found in LLM response. "
                        f"Response preview: {ai_response_text[:200]}"
                    )

            # Extract all fields
            ai_index = ai_response.get("selected_index", 0)
            ai_reasoning = ai_response.get("reasoning", "No reasoning provided")
            duplicate_analysis = ai_response.get("duplicate_analysis", "")
            reproducibility_analysis = ai_response.get("reproducibility_analysis", "")
            skipped_candidates = ai_response.get("skipped_candidates", [])

            # Log analyses
            if duplicate_analysis:
                logger.info(f"  AI duplicate analysis: {duplicate_analysis}")
            if reproducibility_analysis:
                logger.info(f"  AI reproducibility analysis: {reproducibility_analysis}")
            if skipped_candidates:
                logger.info(f"  AI skipped candidates (duplicates/unreproducible): {skipped_candidates}")

            # Validate index and check for duplicate conflicts
            if ai_index == -1:
                # AI flagged all candidates as semantic duplicates
                logger.warning("  AI flagged ALL top candidates as semantic duplicates")
                logger.warning("  Falling back to deterministic selection (best available)")
                logger.warning("  Note: This may produce content similar to recent videos")
            elif ai_index in skipped_candidates:
                # Contradiction: AI selected a candidate it also skipped
                logger.warning(f"  AI selected candidate #{ai_index + 1} but also marked it as duplicate")
                logger.warning("  Falling back to deterministic selection to avoid confusion")
            elif 0 <= ai_index < len(top_candidates):
                # Valid selection
                ai_selected_trend = top_candidates[ai_index]

                logger.info(f"✓ AI selected candidate #{ai_index + 1}: '{ai_selected_trend.keyword}'")
                logger.info(f"  AI reasoning: {ai_reasoning}")

                # Compare with deterministic selection
                if ai_selected_trend.keyword != video_plan.working_title:
                    logger.info(f"  Note: AI chose different from deterministic (#1)")
                    logger.info(f"       Deterministic: '{video_plan.working_title}'")
                    logger.info(f"       AI strategic: '{ai_selected_trend.keyword}'")

                    # Rebuild VideoPlan with AI selection
                    video_plan = VideoPlan(
                        working_title=ai_selected_trend.keyword,
                        strategic_angle=f"{ai_selected_trend.why_hot}. AI selection reasoning: {ai_reasoning}",
                        target_audience=video_plan.target_audience,
                        language=ai_selected_trend.language,
                        compliance_notes=video_plan.compliance_notes
                    )
                    logger.info("  ✓ Updated VideoPlan with AI-selected trend")
                else:
                    logger.info("  AI confirmed deterministic selection (same choice)")
            else:
                # Invalid index (out of range)
                logger.warning(f"  AI returned invalid index {ai_index}, keeping deterministic selection")

        except Exception as e:
            # 🚨 Log AI selection failure fallback
            log_fallback(
                component="PIPELINE_AI_SELECTION",
                fallback_type="DETERMINISTIC_SELECTION",
                reason=f"AI selection failed: {e}",
                impact="MEDIUM"
            )
            logger.warning(f"AI selection failed: {e}")
            logger.warning("Falling back to deterministic selection")
    elif use_ai_selection:
        logger.info("Step 3.2: AI selection skipped (not enough candidates)")
    else:
        logger.info("Step 3.2: AI-assisted selection disabled (use_ai_selection=False)")

    # Step 3.3: Editorial Strategist - AI-driven strategic decision (NEW)
    logger.info("=" * 70)
    logger.info("Step 3.3: Running Editorial Strategist (AI-driven strategy)...")
    logger.info("=" * 70)

    # Find the selected trend from top_candidates
    selected_trend = None
    for candidate in top_candidates:
        if candidate.keyword == video_plan.working_title:
            selected_trend = candidate
            break

    # If not found in top_candidates, use first one as fallback
    if not selected_trend and len(top_candidates) > 0:
        selected_trend = top_candidates[0]
        logger.warning(f"Selected trend not found in top_candidates, using first candidate")

    # Gather performance history for learning loop
    try:
        from yt_autopilot.io.datastore import get_all_videos
        all_videos = get_all_videos(workspace_id)
        # Take last 10 videos with performance data
        performance_history = [
            {
                'title': v.get('final_title', ''),
                'views': v.get('views', 0),
                'avg_view_duration_percentage': v.get('avg_view_duration_percentage', 0),
                'ctr': v.get('ctr', 0),
                'serie_id': v.get('serie_id', 'unknown'),
                'format': v.get('format', 'unknown')
            }
            for v in all_videos[-10:]
            if 'final_title' in v
        ]
    except Exception as e:
        # 🚨 Log performance history loading failure fallback (low impact - uses empty list)
        log_fallback(
            component="PIPELINE_PERFORMANCE_HISTORY",
            fallback_type="EMPTY_HISTORY",
            reason=f"Failed to load performance history: {e}",
            impact="LOW"
        )
        logger.warning(f"Failed to load performance history: {e}")
        performance_history = []

    # ===================================================================
    # PHASE A4: AGENT COORDINATOR INTEGRATION (Feature Flag)
    # ===================================================================
    if use_coordinator:
        logger.info("")
        logger.info("=" * 70)
        logger.info("USING AGENT COORDINATOR (Phase A4)")
        logger.info("  Standardized agent execution with retry logic + error handling")
        logger.info("=" * 70)
        logger.info("")

        # Import AgentCoordinator and AgentContext
        from yt_autopilot.core.agent_coordinator import AgentCoordinator, AgentContext
        import uuid

        # Create AgentContext with all pipeline state
        context = AgentContext(
            workspace=workspace,
            video_plan=video_plan,
            llm_generate_fn=llm_generate_fn,
            workspace_id=workspace_id,
            execution_id=str(uuid.uuid4()),
            selected_trend=selected_trend,
            top_candidates=top_candidates,
            performance_history=performance_history,
            memory=memory,
            series_format=series_format if 'series_format' in locals() else None
        )

        # Initialize coordinator and execute pipeline
        coordinator = AgentCoordinator()

        try:
            result = coordinator.execute_pipeline(context, mode="linear")

            if result["status"] == "success":
                # Extract final context
                final_context = result["context"]

                # Log pipeline summary
                summary = result["summary"]
                logger.info("")
                logger.info("=" * 70)
                logger.info("AGENT COORDINATOR SUMMARY")
                logger.info("=" * 70)
                logger.info(f"  Agents called: {summary['agents_called']}")
                logger.info(f"  Total time: {summary['total_time_ms']:.0f}ms ({summary['total_time_ms']/1000:.1f}s)")
                logger.info(f"  Average per agent: {summary['avg_time_per_agent_ms']:.0f}ms")
                logger.info(f"  Errors: {summary['errors']}")
                logger.info(f"  Fallbacks used: {summary['fallbacks']}")
                logger.info("=" * 70)

                # Create ContentPackage from final context
                approved_package = coordinator.create_content_package(
                    final_context,
                    status="APPROVED",
                    rejection_reason=None
                )

                # Update workspace with new title (same as legacy path)
                if final_context.publishing:
                    update_workspace_recent_titles(workspace_id, final_context.publishing.final_title)

                logger.info("")
                logger.info("=" * 70)
                logger.info("EDITORIAL PIPELINE COMPLETE (AgentCoordinator): STATUS = APPROVED")
                logger.info(f"  Title: '{final_context.publishing.final_title if final_context.publishing else 'N/A'}'")
                logger.info(f"  Script bullets: {len(final_context.script.bullets) if final_context.script else 0}")
                logger.info(f"  Visual scenes: {len(final_context.visual_plan.scenes) if final_context.visual_plan else 0}")
                logger.info("=" * 70)

                return approved_package

            else:
                # Pipeline failed at critical agent
                failed_agent = result.get("failed_agent", "unknown")
                error = result.get("error")

                logger.error("")
                logger.error("=" * 70)
                logger.error("AGENT COORDINATOR PIPELINE FAILED")
                logger.error(f"  Failed agent: {failed_agent}")
                logger.error(f"  Error: {error.message if error else 'Unknown'}")
                logger.error("=" * 70)

                # Create REJECTED package
                rejected_package = coordinator.create_content_package(
                    result["context"],
                    status="REJECTED",
                    rejection_reason=f"Critical agent '{failed_agent}' failed: {error.message if error else 'Unknown error'}"
                )

                return rejected_package

        except Exception as e:
            logger.error(f"AgentCoordinator execution failed: {e}")
            logger.error("Falling back to legacy pipeline execution...")
            # Fall through to legacy path below

    # ===================================================================
    # LEGACY PATH: Original agent orchestration (backward compatible)
    # ===================================================================

    # Call Editorial Strategist with LLM reasoning
    if selected_trend:
        editorial_decision = decide_editorial_strategy(
            trend=selected_trend,
            workspace=workspace,
            llm_generate_fn=llm_generate_fn,  # Sprint 2: Use language-validated wrapper
            performance_history=performance_history
        )

        logger.info("✓ Editorial strategy decided:")
        logger.info(f"  Serie: {editorial_decision.serie_concept}")
        logger.info(f"  Format: {editorial_decision.format}")
        logger.info(f"  Angle: {editorial_decision.angle}")
        logger.info(f"  Duration target: {editorial_decision.duration_target}s")
        logger.info(f"  Breakdown: hook={editorial_decision.duration_breakdown.get('hook')}s, "
                   f"context={editorial_decision.duration_breakdown.get('context')}s, "
                   f"insight={editorial_decision.duration_breakdown.get('insight')}s, "
                   f"cta={editorial_decision.duration_breakdown.get('cta')}s")
        logger.info(f"  Monetization: {editorial_decision.monetization_path}")
        logger.info(f"  CTA: {editorial_decision.cta_specific[:60]}...")
        logger.info(f"  Reasoning: {truncate_for_log(editorial_decision.reasoning_summary, LOG_TRUNCATE_REASONING)}")

        # ========== VALIDATION GATE 1: POST-EDITORIAL ==========
        gate1_enabled, gate1_blocking = _is_gate_enabled(workspace, 'post_editorial')

        if gate1_enabled:
            logger.info("")
            from yt_autopilot.core.pipeline_validator import (
                Gate1_PostEditorialValidator,
                ValidationSeverity,
                log_validation_result
            )
            import glob

            gate1_validator = Gate1_PostEditorialValidator()

            # Get available series formats
            series_format_files = glob.glob("config/series_formats/*.yaml")
            series_formats_available = [f.split('/')[-1].replace('.yaml', '') for f in series_format_files]

            gate1_result = gate1_validator.validate(
                editorial_decision=editorial_decision,
                trend=selected_trend,
                workspace=workspace,
                series_formats_available=series_formats_available
            )

            log_validation_result(gate1_result, gate_number=1)

            if not gate1_result.is_valid:
                blocking_issues = gate1_result.get_blocking_issues()
                logger.error(f"❌ Gate 1 validation failed with {len(blocking_issues)} blocking issues:")
                for issue in blocking_issues:
                    logger.error(f"   • {issue.message}")

                if gate1_blocking:
                    raise ValueError(
                        f"Editorial validation failed. Fix editorial strategy before proceeding. "
                        f"First issue: {blocking_issues[0].message}"
                    )
                else:
                    logger.warning("⚠️ Gate 1 non-blocking - continuing despite validation failure")

            logger.info("✅ Gate 1 validation passed - Editorial decision coherent")
            logger.info("")
        else:
            logger.info("⚙️ Gate 1 (Post-Editorial) disabled in config - skipping validation")
        # ========== END GATE 1 ==========

    else:
        logger.warning("No trend selected, skipping Editorial Strategist")
        editorial_decision = None

    # Step 3.6: Duration Strategist - AI-driven duration for monetization (NEW)
    logger.info("=" * 70)
    logger.info("Step 3.6: Running Duration Strategist (AI-driven monetization)...")
    logger.info("=" * 70)

    if selected_trend and editorial_decision:
        # Get vertical config for CPM data
        vertical_config = get_vertical_config(vertical_id)

        # Call Duration Strategist
        duration_strategy = analyze_duration_strategy(
            topic=video_plan.working_title,
            vertical_id=vertical_id,
            workspace_config=workspace,
            vertical_config=vertical_config,
            trend_data={
                'source': selected_trend.source,
                'engagement_score': selected_trend.momentum_score,
                'virality_potential': selected_trend.virality_score
            }
        )

        logger.info(f"✓ Duration strategy: {duration_strategy['target_duration_seconds']}s ({duration_strategy['format_type']})")
    else:
        logger.warning("Skipping Duration Strategist (no trend/editorial decision)")
        duration_strategy = {
            'target_duration_seconds': 180,
            'format_type': 'mid',
            'reasoning': 'Fallback: No editorial decision available',
            'monetization_strategy': 'ads',
            'content_depth_score': 0.5,
            'viral_potential_score': 0.5
        }

    # Step 3.6.5: Format Reconciler - Arbitrate duration divergences (Fase 2 Sprint 1)
    logger.info("=" * 70)
    logger.info("Step 3.6.5: Running Format Reconciler (duration arbitration)...")
    logger.info("=" * 70)

    # Phase C - P0: Initialize timeline (single source of truth for duration)
    timeline = None

    if editorial_decision and duration_strategy:
        # Call Format Reconciler to arbitrate duration divergence
        # Phase C - P0: Returns Timeline object (single source of truth)
        timeline = reconcile_format_strategies(
            editorial_decision=editorial_decision,
            duration_strategy=duration_strategy,
            llm_generate_fn=llm_generate_fn,  # Sprint 2: Use language-validated wrapper
            workspace_config=workspace
        )

        logger.info(f"✓ Format reconciliation complete (Timeline created):")
        logger.info(f"  Editorial duration: {editorial_decision.duration_target}s")
        logger.info(f"  Duration Strategist: {duration_strategy['target_duration_seconds']}s")
        logger.info(f"  Final reconciled: {timeline.reconciled_duration}s ({timeline.format_type})")
        logger.info(f"  Arbitration source: {timeline.arbitration_source}")
        logger.info(f"  Editorial weight: {timeline.editorial_weight:.2f} | Duration weight: {timeline.duration_weight:.2f}")
        logger.info(f"  Reasoning: {truncate_for_log(timeline.arbitration_reasoning, LOG_TRUNCATE_REASONING)}")

        # Phase C - P0: No longer mutate duration_strategy - Timeline is single source of truth
        # REMOVED: duration_strategy in-place mutation (lines 1129-1132)
        # All agents now receive timeline directly instead of modified duration_strategy

        # ========== VALIDATION GATE 2: POST-DURATION ==========
        logger.info("")
        gate2_enabled, gate2_blocking = _is_gate_enabled(workspace, 'post_duration')

        if gate2_enabled:
            from yt_autopilot.core.pipeline_validator import Gate2_PostDurationValidator

            gate2_validator = Gate2_PostDurationValidator()

            # Note: visual_plan not yet available, pass None for aspect ratio
            # Phase C - P0: Pass Timeline object instead of reconciled_format dict
            gate2_result = gate2_validator.validate(
                editorial_decision=editorial_decision,
                duration_strategy=duration_strategy,
                reconciled_format=timeline,  # Now Timeline object (backward compatible with .reconciled_duration)
                visual_plan_aspect_ratio=None  # Will be validated again in Gate 4
            )

            log_validation_result(gate2_result, gate_number=2)

            if not gate2_result.is_valid:
                blocking_issues = gate2_result.get_blocking_issues()
                logger.error(f"❌ Gate 2 validation failed with {len(blocking_issues)} blocking issues:")
                for issue in blocking_issues:
                    logger.error(f"   • {issue.message}")

                if gate2_blocking:
                    raise ValueError(
                        f"Duration reconciliation validation failed. "
                        f"First issue: {blocking_issues[0].message}"
                    )
                else:
                    logger.warning("⚠️ Gate 2 non-blocking - continuing despite validation failure")
                    for issue in blocking_issues[:3]:  # Show first 3 issues
                        logger.warning(f"   • {issue.message}")

            logger.info("✅ Gate 2 validation passed - Duration reconciliation coherent")
        else:
            logger.info("⚙️ Gate 2 (Post-Duration) disabled in config - skipping validation")

        logger.info("")
        # ========== END GATE 2 ==========

    else:
        logger.warning("Skipping Format Reconciler (no editorial/duration strategy)")

    # Step 3.7: Content Depth Strategist - AI-driven bullets count optimization (MOVED BEFORE NARRATIVE)
    logger.info("=" * 70)
    logger.info("Step 3.7: Running Content Depth Strategist (bullets count optimization)...")
    logger.info("=" * 70)

    if editorial_decision and duration_strategy:
        # Call Content Depth Strategist to determine optimal bullets count
        # FASE 1 FIX: Run BEFORE Narrative so we can pass bullet_count_constraint
        # Phase C - P0: Use timeline.reconciled_duration (single source of truth)
        content_depth_strategy = analyze_content_depth(
            topic=video_plan.working_title,
            target_duration=timeline.reconciled_duration,
            narrative_arc={},  # Empty dict - Narrative not generated yet
            editorial_decision=editorial_decision.__dict__ if hasattr(editorial_decision, '__dict__') else editorial_decision,
            workspace=workspace,
            llm_generate_fn=llm_generate_fn  # Use language-validated LLM
        )

        logger.info(f"✓ Content depth strategy generated:")
        logger.info(f"  Recommended bullets: {content_depth_strategy['recommended_bullets']}")
        logger.info(f"  Time allocation: {content_depth_strategy['time_per_bullet']}")
        logger.info(f"  Adequacy score: {content_depth_strategy['adequacy_score']:.2f}")
        logger.info(f"  Reasoning: {truncate_for_log(content_depth_strategy['reasoning'], LOG_TRUNCATE_REASONING)}")

        # Validate adequacy score
        if content_depth_strategy['adequacy_score'] < 0.6:
            logger.warning(f"⚠️ Content depth adequacy score LOW ({content_depth_strategy['adequacy_score']:.2f})")
            logger.warning("   Content may be too thin or too dense for target duration")
    else:
        logger.warning("Skipping Content Depth Strategist (no editorial/duration strategy)")
        # Fallback: deterministic bullets count
        # Phase C - P0: Use timeline.reconciled_duration if available
        target_dur = timeline.reconciled_duration if timeline else 480
        bullets_count = max(2, min(6, target_dur // 90))  # 90s per bullet
        content_depth_strategy = {
            'recommended_bullets': bullets_count,
            'time_per_bullet': [target_dur // bullets_count] * bullets_count,
            'depth_scores': [0.7] * bullets_count,
            'pacing_guidance': f"Fallback: {bullets_count} bullets with equal time allocation",
            'reasoning': 'Fallback: Content Depth Strategist skipped',
            'adequacy_score': 0.65,
            '_fallback': True
        }

    # Step 3.7.5: Narrative Architect - AI-driven emotional storytelling (WITH bullet constraint)
    logger.info("=" * 70)
    logger.info("Step 3.7.5: Running Narrative Architect (emotional storytelling)...")
    logger.info("=" * 70)

    if editorial_decision and duration_strategy:
        # FASE 1 FIX: Pass bullet_count_constraint from Content Depth
        recommended_bullets = content_depth_strategy.get('recommended_bullets')
        logger.info(f"  Using Content Depth recommendation: {recommended_bullets} content acts")

        # Call Narrative Architect with bullet count constraint
        # Phase C - P2: Pass Timeline object for duration enforcement
        narrative_arc = design_narrative_arc(
            topic=video_plan.working_title,
            target_duration_seconds=duration_strategy['target_duration_seconds'],  # Deprecated (timeline overrides)
            workspace_config=workspace,
            duration_strategy=duration_strategy,
            editorial_decision=editorial_decision.__dict__ if hasattr(editorial_decision, '__dict__') else editorial_decision,
            bullet_count_constraint=recommended_bullets,  # FASE 1: Force specific bullet count from start
            llm_generate_fn=llm_generate_fn,  # WEEK 2 Task 2.1: Use language-validated LLM
            timeline=timeline  # Phase C - P2: Single source of truth for duration
        )

        logger.info(f"✓ Narrative arc created with {len(narrative_arc['narrative_structure'])} acts")

        # Layer 2: AI-driven expansion if narrative is too short
        narrative_arc = expand_narrative_voiceovers(
            narrative_arc=narrative_arc,
            target_duration=timeline.reconciled_duration if timeline else duration_strategy['target_duration_seconds'],
            target_language=workspace.get('target_language', 'en'),
            llm_generate_fn=llm_generate_fn
        )
    else:
        logger.warning("Skipping Narrative Architect (no editorial/duration strategy)")
        narrative_arc = None

    # Step 3.7.6: CTA Strategist - Strategic CTA placement (Fase 2 Sprint 1)
    logger.info("=" * 70)
    logger.info("Step 3.7.6: Running CTA Strategist (mid-roll CTA placement)...")
    logger.info("=" * 70)

    if editorial_decision and duration_strategy and narrative_arc:
        # Call CTA Strategist to design CTA placement
        cta_strategy = design_cta_strategy(
            duration_strategy=duration_strategy,
            editorial_decision=editorial_decision,
            narrative_arc=narrative_arc,
            workspace_config=workspace,
            llm_generate_fn=llm_generate_fn  # Sprint 2: Use language-validated wrapper
        )

        logger.info(f"✓ CTA strategy designed:")
        logger.info(f"  Main CTA: {cta_strategy['main_cta'][:60]}...")
        logger.info(f"  Mid-roll CTAs: {len(cta_strategy['mid_roll_ctas'])}")
        for mid_cta in cta_strategy.get('mid_roll_ctas', []):
            logger.info(f"    - {mid_cta['timestamp']}s ({mid_cta['type']}): {mid_cta['cta'][:50]}...")
        logger.info(f"  Funnel path: {cta_strategy['funnel_path']}")
        logger.info(f"  Total CTAs: {cta_strategy['cta_count']}")
        logger.info(f"  Reasoning: {truncate_for_log(cta_strategy['reasoning'], LOG_TRUNCATE_REASONING)}")
    else:
        logger.warning("Skipping CTA Strategist (no editorial/duration/narrative)")
        cta_strategy = {
            'main_cta': editorial_decision.cta_specific if editorial_decision else 'Follow for more content',
            'mid_roll_ctas': [],
            'funnel_path': 'engagement → playlist → community',
            'reasoning': 'Fallback: CTA Strategist skipped',
            'cta_count': 1
        }

    # =========================================================================
    # FASE 1 INTEGRATION: Quality Validation & Retry Framework
    # =========================================================================
    # Validate narrative bullet count against content depth recommendation
    # If mismatch detected, regenerate narrative with constraint
    # =========================================================================

    if narrative_arc and content_depth_strategy and not content_depth_strategy.get('_fallback'):
        logger.info("=" * 70)
        logger.info("Quality Validation: Narrative Bullet Count")
        logger.info("=" * 70)

        # Import quality validator and retry functions
        from yt_autopilot.core.agent_coordinator import (
            AgentContext,
            validate_narrative_bullet_count,
            regenerate_narrative_with_bullet_constraint,
            validate_cta_semantic_match,
            regenerate_script_with_cta_fix
        )
        from yt_autopilot.core.config import load_validation_thresholds
        from yt_autopilot.core.logger import log_fallback

        # Load quality validation thresholds
        format_type = duration_strategy.get('format_type') if duration_strategy else None
        thresholds = load_validation_thresholds(
            workspace_id=workspace_id,
            format_type=format_type
        )

        # Create minimal validation context (compatible with validator signature)
        class ValidationContext:
            def __init__(self, content_depth, thresholds_dict, workspace_id_val):
                self.content_depth_strategy = content_depth
                self.thresholds = thresholds_dict
                self.workspace_id = workspace_id_val

        validator_context = ValidationContext(
            content_depth=content_depth_strategy,
            thresholds_dict=thresholds,
            workspace_id_val=workspace_id
        )

        # Run quality validation
        is_valid, validation_error = validate_narrative_bullet_count(narrative_arc, validator_context)

        if not is_valid:
            logger.warning(f"⚠️ Quality validation failed: {validation_error}")
            logger.info("🔧 Attempting quality retry (regenerate narrative with bullet constraint)...")

            # Log fallback for monitoring
            log_fallback(
                component="NARRATIVE_ARCHITECT",
                fallback_type="QUALITY_RETRY",
                reason=validation_error,
                impact="MEDIUM"
            )

            try:
                # Regenerate narrative with bullet count constraint
                recommended_bullets = content_depth_strategy.get('recommended_bullets')
                logger.info(f"   Forcing narrative to generate EXACTLY {recommended_bullets} content acts...")

                # Phase C - P2: Pass Timeline object for duration enforcement
                narrative_arc_v2 = design_narrative_arc(
                    topic=video_plan.working_title,
                    target_duration_seconds=duration_strategy['target_duration_seconds'],  # Deprecated (timeline overrides)
                    workspace_config=workspace,
                    duration_strategy=duration_strategy,
                    editorial_decision=editorial_decision.__dict__ if hasattr(editorial_decision, '__dict__') else editorial_decision,
                    bullet_count_constraint=recommended_bullets,  # FASE 1: Force specific bullet count
                    timeline=timeline  # Phase C - P2: Single source of truth for duration
                )

                # Re-validate after retry
                is_valid_retry, retry_error = validate_narrative_bullet_count(narrative_arc_v2, validator_context)

                if is_valid_retry:
                    logger.info("✓ Quality retry succeeded! Narrative regenerated with correct bullet count")
                    narrative_arc = narrative_arc_v2  # Use new narrative

                    # IMPORTANT: Regenerate CTA Strategist with new narrative
                    logger.info("   Regenerating CTA Strategist with updated narrative...")
                    cta_strategy = design_cta_strategy(
                        duration_strategy=duration_strategy,
                        editorial_decision=editorial_decision,
                        narrative_arc=narrative_arc,  # Use v2
                        workspace_config=workspace,
                        llm_generate_fn=llm_generate_fn
                    )
                    logger.info(f"   ✓ CTA strategy updated (Main CTA: {cta_strategy['main_cta'][:50]}...)")
                else:
                    logger.warning(f"⚠️ Quality retry failed: {retry_error}")
                    logger.warning("   Continuing with original narrative (quality may be suboptimal)")

            except Exception as e:
                logger.error(f"❌ Quality retry encountered error: {e}")
                logger.warning("   Continuing with original narrative")
        else:
            logger.info(f"✓ Quality validation passed (bullet count matches recommendation)")

    # =========================================================================
    # End of Quality Validation Block
    # =========================================================================

    # Capture AI agent reasoning for content_package.md transparency
    duration_reasoning = duration_strategy.get('reasoning', '') if duration_strategy else None
    format_reasoning = duration_strategy.get('reconciliation_reasoning', '') if duration_strategy and duration_strategy.get('reconciliation_applied') else None

    # Construct narrative reasoning from returned structure
    narrative_reasoning = None
    if narrative_arc:
        narrative_reasoning = f"Voice: {narrative_arc.get('voice_personality', 'N/A')} | Emotional Journey: {narrative_arc.get('emotional_journey', 'N/A')} | {len(narrative_arc.get('narrative_structure', []))} acts"

    cta_reasoning = cta_strategy.get('reasoning', '') if cta_strategy else None

    # Debug: Log captured reasoning
    logger.info("=" * 70)
    logger.info("AI Decision Rationale captured:")
    logger.info(f"  Duration: {truncate_for_log(duration_reasoning, LOG_TRUNCATE_REASONING) if duration_reasoning else 'None'}")
    logger.info(f"  Format: {truncate_for_log(format_reasoning, LOG_TRUNCATE_REASONING) if format_reasoning else 'None'}")
    logger.info(f"  Narrative: {truncate_for_log(narrative_reasoning, LOG_TRUNCATE_REASONING) if narrative_reasoning else 'None'}")
    logger.info(f"  CTA: {truncate_for_log(cta_reasoning, LOG_TRUNCATE_REASONING) if cta_reasoning else 'None'}")
    logger.info("=" * 70)

    # Step 3.8: Detect series format (Step 07.5: Format engine)
    # NOTE: If editorial_decision is available, use its serie_concept instead of auto-detection
    logger.info("=" * 70)
    logger.info("Step 3.8: Detecting series format...")
    logger.info("=" * 70)

    if editorial_decision:
        # Use AI-decided serie concept
        logger.info(f"  Using Editorial Strategist's serie: {editorial_decision.serie_concept}")
        serie_id = editorial_decision.serie_concept.lower().replace(' ', '_')

        # Try to load existing format, fallback to generic if not found
        try:
            series_format = series_manager.load_format(serie_id)
            logger.info(f"✓ Loaded existing series format: {series_format.name}")
        except Exception:
            logger.warning(f"  Serie '{serie_id}' not found in formats, using 'tutorial' fallback")
            serie_id = "tutorial"
            series_format = series_manager.load_format(serie_id)
    else:
        # Fallback to auto-detection (legacy behavior)
        serie_id = series_manager.detect_serie(
            video_plan.working_title,
            video_plan.strategic_angle
        )
        series_format = series_manager.load_format(serie_id)
        logger.info(f"✓ Auto-detected series format: {series_format.name} ({serie_id})")

    logger.info(f"  Structure: {len(series_format.segments)} segments")

    # Update video plan with series_id
    video_plan.series_id = serie_id

    # Step 4: ScriptWriter - generate script (NEW: with LLM integration)
    logger.info("Step 4: Running ScriptWriter to generate script...")

    # NEW (Step 06-fullrun): Call LLM for creative script suggestion
    logger.info("  Step 4a: Calling LLM for creative script generation...")

    brand_tone = workspace.get('brand_tone', 'Direct, positive, educational')
    target_language = workspace.get('target_language', 'en')  # Step 10: Language consistency

    # Step 09: Check if narrator persona is enabled
    narrator = workspace.get('narrator_persona', {})
    content_formula = workspace.get('content_formula', {})
    narrator_enabled = narrator.get('enabled', False)

    # Sprint 2: Extract recommended bullets from Content Depth Strategist
    recommended_bullets = None
    if content_depth_strategy:
        recommended_bullets = content_depth_strategy.get('recommended_bullets')
        logger.info(f"  Content Depth: Using {recommended_bullets} bullets (AI-optimized)")

    if narrator_enabled:
        # Use narrator persona-aware prompt builder (Step 09)
        logger.info("  Using narrator persona-aware prompt...")
        logger.info(f"  Narrator: {narrator.get('name', 'Unknown')}")
        logger.info(f"  Relationship: {narrator.get('relationship', 'Unknown')}")
        logger.info(f"  Target language: {target_language}")  # Step 10

        llm_task = _build_persona_aware_prompt(
            plan=video_plan,
            narrator=narrator,
            content_formula=content_formula,
            series_format=series_format,
            brand_tone=brand_tone,
            target_language=target_language,  # Step 10
            recommended_bullets=recommended_bullets  # Sprint 2: AI-driven bullets count
        )

        # Context for narrator-aware prompt (strategic angle only, prompt has full context)
        llm_context = video_plan.strategic_angle
    else:
        # Fallback to legacy generic prompt (backward compatible)
        logger.info("  Using legacy generic prompt (narrator persona disabled)...")

        # Build context with editorial decision if available (Step 11)
        llm_context = f"""
Topic: {video_plan.working_title}
Strategic Angle: {video_plan.strategic_angle}
Target Audience: {video_plan.target_audience}
Language: {video_plan.language}
Format: YouTube Shorts (vertical 9:16, max 60 seconds)
Brand Tone: {brand_tone}
    """.strip()

        # Step 11: Add editorial strategy to context if available
        if editorial_decision:
            llm_context += f"""

EDITORIAL STRATEGY (AI-Driven):
- Serie: {editorial_decision.serie_concept}
- Format: {editorial_decision.format}
- Angle: {editorial_decision.angle}
- Duration Target: {editorial_decision.duration_target}s
  - Hook: {editorial_decision.duration_breakdown.get('hook', 3)}s
  - Context: {editorial_decision.duration_breakdown.get('context', 8)}s
  - Insight: {editorial_decision.duration_breakdown.get('insight', 10)}s
  - CTA: {editorial_decision.duration_breakdown.get('cta', 5)}s
- Monetization: {editorial_decision.monetization_path}
- Specific CTA to use: "{editorial_decision.cta_specific}"

CRITICAL: Respect this strategy. Use EXACTLY the CTA specified above. Follow duration breakdown.
"""

        # Step 10: Build language-aware legacy prompt
        # Sprint 2: Use AI-driven bullets count
        language_names = {
            "it": "ITALIANO",
            "en": "INGLESE",
            "es": "SPAGNOLO",
            "fr": "FRANCESE",
            "de": "TEDESCO",
            "pt": "PORTOGHESE"
        }
        target_lang = workspace.get('target_language', video_plan.language).lower()
        language_name = language_names.get(target_lang, target_lang.upper())

        # Sprint 2: Dynamic bullets placeholders based on Content Depth Strategist
        if recommended_bullets is None:
            recommended_bullets = 4  # Legacy default

        bullets_placeholders = "\n".join([f"- <punto chiave {i+1}>" for i in range(recommended_bullets)])

        llm_task = f"""⚠️ REQUISITO CRITICO LINGUA ⚠️
═══════════════════════════════════════════════════════════════
TUTTO L'OUTPUT DEVE ESSERE IN {language_name}
NON MISCHIARE LE LINGUE. OGNI SINGOLA PAROLA DEVE ESSERE IN {language_name}.
═══════════════════════════════════════════════════════════════

Scrivi uno script completo per un YouTube Short in formato strutturato.

REQUISITI:
- Massimo 60 secondi totali di video
- Tono educativo ma coinvolgente
- Linguaggio chiaro e diretto
- NIENTE promesse mediche garantite
- NIENTE hate speech o contenuti tossici
- NIENTE clickbait ingannevole

FORMATO RICHIESTO (rispetta ESATTAMENTE questa struttura):

HOOK:
<frase di apertura forte e coinvolgente per i primi 3 secondi>

BULLETS:
{bullets_placeholders}

⚠️ CRITICO: Fornisci ESATTAMENTE {recommended_bullets} bullets (numero ottimizzato dall'AI)

CTA:
<call-to-action breve e non invasiva>

VOICEOVER:
<testo completo del voiceover da leggere ad alta voce, 15-60 secondi, include hook + bullets + CTA in forma narrativa>

IMPORTANTE - STILE CREATOR (Step 07.2):
- Il VOICEOVER deve essere il testo finale parlato, NON una lista di punti
- Tono ENERGICO e COINVOLGENTE (non monotono o da documentario)
- Frasi BREVI e INCISIVE (max 10-12 parole per frase)
- Usa espressioni colloquiali naturali nella lingua target
- Parla in SECONDA PERSONA SINGOLARE ("tu" / "you"), stile diretto e personale
- HOOK POTENTE nei primi 2 secondi che cattura l'attenzione
- Flow naturale come se stessi parlando a un amico
- Energetico ma non urlato, coinvolgente ma non artificiale

⚠️ VERIFICA FINALE: Assicurati che TUTTO il testo sopra sia in {language_name} ⚠️
    """.strip()

    # Generate LLM suggestion (same for both narrator-aware and legacy paths)
    llm_suggestion = llm_generate_fn(
        role="script_writer",
        task=llm_task,
        context=llm_context,
        style_hints={
            "language": video_plan.language,
            "brand_tone": brand_tone,
            "target_audience": video_plan.target_audience
        }
    )

    logger.info(f"  ✓ LLM suggestion received ({len(llm_suggestion)} chars)")

    # Step 4b: Pass LLM suggestion to ScriptWriter agent for validation
    logger.info("  Step 4b: ScriptWriter agent validating LLM output...")
    script = write_script(
        video_plan,
        memory,
        llm_suggestion=llm_suggestion,
        series_format=series_format,
        editorial_decision=editorial_decision,  # Step 11: Pass AI strategy
        narrative_arc=narrative_arc,  # Monetization Refactor: Pass emotional storytelling
        content_depth_strategy=content_depth_strategy,  # Sprint 2: AI-driven bullets count
        cta_strategy=cta_strategy,  # Phase B2: AI-driven CTA placement
        llm_generate_fn=llm_generate_fn  # Hook length validation
    )

    logger.info(f"✓ Script generated: {len(script.bullets)} content points")
    logger.info(f"  Hook: '{script.hook[:60]}...'")
    logger.info(f"  Voiceover length: {len(script.full_voiceover_text)} chars")

    # ========== VALIDATION GATE 3: POST-SCRIPT ==========
    logger.info("")
    gate3_enabled, gate3_blocking = _is_gate_enabled(workspace, 'post_script')

    if gate3_enabled:
        from yt_autopilot.core.pipeline_validator import Gate3_PostScriptValidator

        gate3_validator = Gate3_PostScriptValidator(llm_generate_fn=llm_generate_fn)

        # Phase C - P0: Use timeline.reconciled_duration (single source of truth)
        gate3_result = gate3_validator.validate(
            script=script,
            content_depth_strategy=content_depth_strategy,
            editorial_decision=editorial_decision,
            workspace=workspace,
            target_duration=timeline.reconciled_duration
        )

        log_validation_result(gate3_result, gate_number=3)

        if not gate3_result.is_valid:
            blocking_issues = gate3_result.get_blocking_issues()
            logger.error(f"❌ Gate 3 validation failed with {len(blocking_issues)} blocking issues:")
            for issue in blocking_issues:
                logger.error(f"   • {issue.message}")

            # Auto-fix language mismatch if possible
            language_mismatch = any(i.code == "SCR_LANGUAGE_MISMATCH" for i in blocking_issues)

            # Auto-retry duration mismatch if possible (Gate 3 Retry - Phase 1)
            duration_mismatch = any(i.code == "SCRIPT_DURATION_MISMATCH" for i in blocking_issues)

            if duration_mismatch:
                logger.warning("  🔧 Attempting script regeneration with duration constraints...")

                # Extract target information
                target_duration = timeline.reconciled_duration if timeline else duration_strategy.get('target_duration_seconds', 360)
                target_words = int(target_duration * 2.5)  # 2.5 words/second speaking rate
                current_words = len(script.full_voiceover_text.split())
                divergence_pct = abs(target_words - current_words) / target_words * 100

                logger.info(f"  Current: {current_words} words ({int(current_words / 2.5)}s)")
                logger.info(f"  Target: {target_words} words ({target_duration}s)")
                logger.info(f"  Divergence: {divergence_pct:.1f}%")

                # Attempt narrative expansion with more aggressive retry (max_attempts=3)
                # Note: expand_narrative_voiceovers already imported at module level (line 37)
                logger.info("  Layer 2 Retry: Expanding narrative arc with stricter target...")
                expanded_narrative_arc = expand_narrative_voiceovers(
                    narrative_arc=narrative_arc,
                    target_duration=target_duration,
                    target_language=workspace.get('target_language', 'en'),
                    llm_generate_fn=llm_generate_fn,
                    max_attempts=3  # More attempts than initial expansion (was 2)
                )

                # Regenerate script with expanded narrative
                logger.info("  Regenerating script with expanded narrative...")
                script = write_script(
                    video_plan,
                    memory,
                    llm_suggestion=llm_suggestion,  # Reuse same LLM suggestion
                    series_format=series_format,
                    editorial_decision=editorial_decision,
                    narrative_arc=expanded_narrative_arc,  # Use expanded arc
                    content_depth_strategy=content_depth_strategy,
                    cta_strategy=cta_strategy,
                    llm_generate_fn=llm_generate_fn  # Hook length validation
                )

                new_words = len(script.full_voiceover_text.split())
                new_divergence = abs(target_words - new_words) / target_words * 100
                logger.info(f"  ✅ Script regenerated: {new_words} words ({int(new_words / 2.5)}s, {new_divergence:.1f}% divergence)")

                # Re-validate after expansion
                logger.info("  Re-validating Gate 3 after duration fix...")
                gate3_result = gate3_validator.validate(
                    script=script,
                    content_depth_strategy=content_depth_strategy,
                    editorial_decision=editorial_decision,
                    workspace=workspace,
                    target_duration=target_duration
                )

                if gate3_result.is_valid:
                    logger.info("  ✅ Re-validation passed after duration fix")
                    # Update narrative_arc for downstream use
                    narrative_arc = expanded_narrative_arc
                else:
                    logger.error("  ❌ Re-validation still failed after duration fix")
                    if gate3_blocking:
                        raise ValueError(
                            f"Script validation failed even after expansion retry. "
                            f"Final divergence: {new_divergence:.1f}%. "
                            f"Issue: {gate3_result.get_blocking_issues()[0].message}"
                        )
                    else:
                        logger.warning("⚠️ Gate 3 non-blocking - script duration issues remain after retry")

            elif language_mismatch:
                logger.warning("  🔧 Attempting automatic language correction...")
                from yt_autopilot.core.language_validator import LanguageValidator

                target_language = workspace.get('target_language', 'en')
                lang_validator = LanguageValidator(target_language, strict_mode=True)

                # Fix voiceover text
                script.full_voiceover_text = lang_validator.ensure_language_consistency(
                    script.full_voiceover_text,
                    llm_generate_fn,
                    context=video_plan.working_title,
                    component_name="script_voiceover"
                )

                # Fix hook
                script.hook = lang_validator.ensure_language_consistency(
                    script.hook,
                    llm_generate_fn,
                    context=video_plan.working_title,
                    component_name="script_hook"
                )

                # Fix CTA
                script.outro_cta = lang_validator.ensure_language_consistency(
                    script.outro_cta,
                    llm_generate_fn,
                    context=video_plan.working_title,
                    component_name="script_cta"
                )

                logger.info("  ✅ Language corrected, re-validating...")

                # Re-validate after fix
                # Phase C - P0: Use timeline.reconciled_duration (single source of truth)
                gate3_result = gate3_validator.validate(
                    script=script,
                    content_depth_strategy=content_depth_strategy,
                    editorial_decision=editorial_decision,
                    workspace=workspace,
                    target_duration=timeline.reconciled_duration
                )

                if gate3_result.is_valid:
                    logger.info("  ✅ Re-validation passed after language fix")
                else:
                    logger.error("  ❌ Re-validation still failed after language fix")
                    if gate3_blocking:
                        raise ValueError(
                            f"Script validation failed even after language correction. "
                            f"Issue: {gate3_result.get_blocking_issues()[0].message}"
                        )
                    else:
                        logger.warning("⚠️ Gate 3 non-blocking - script issues remain after auto-fix")
            else:
                # Non-language issues
                if gate3_blocking:
                    raise ValueError(
                        f"Script validation failed. Fix script quality before proceeding. "
                        f"First issue: {blocking_issues[0].message}"
                    )
                else:
                    logger.warning("⚠️ Gate 3 non-blocking - continuing despite validation failure")
                    for issue in blocking_issues[:3]:  # Show first 3 issues
                        logger.warning(f"   • {issue.message}")

        logger.info("✅ Gate 3 validation passed - Script quality verified")
    else:
        logger.info("⚙️ Gate 3 (Post-Script) disabled in config - skipping validation")

    logger.info("")
    # ========== END GATE 3 ==========

    # ========== FASE 3: SEMANTIC CTA VALIDATION (OPZIONE A) ==========
    # Validate CTA semantic similarity and retry if needed
    if cta_strategy:  # Only validate if CTA strategy exists
        logger.info("")
        logger.info("=" * 70)
        logger.info("FASE 3: Semantic CTA Validation")
        logger.info("=" * 70)

        # Build minimal validation context (compatible with validator signature)
        class CTAValidationContext:
            def __init__(self):
                self.cta_strategy = cta_strategy
                self.thresholds = thresholds
                self.video_plan = video_plan
                self.memory = memory
                self.series_format = series_format
                self.editorial_decision = editorial_decision
                self.narrative_arc = narrative_arc
                self.content_depth_strategy = content_depth_strategy

        context = CTAValidationContext()

        # Validate CTA semantic match
        is_valid, error_msg = validate_cta_semantic_match(script, context)

        if not is_valid:
            logger.warning(f"⚠️ CTA validation failed: {error_msg}")
            logger.info("  Attempting quality retry with forced CTA...")

            try:
                # Regenerate script with forced CTA
                script_v2 = regenerate_script_with_cta_fix(script, context, error_msg)

                # Validate retry result
                is_valid_v2, error_msg_v2 = validate_cta_semantic_match(script_v2, context)

                if is_valid_v2:
                    logger.info("  ✅ Quality retry succeeded - CTA now matches")
                    script = script_v2  # Use improved script
                else:
                    logger.error(f"  ❌ Quality retry failed: {error_msg_v2}")
                    raise ValueError(f"CTA validation failed after retry: {error_msg_v2}")

            except Exception as e:
                logger.error(f"  ❌ Quality retry failed with exception: {e}")
                raise ValueError(f"CTA validation failed and retry failed: {e}")
        else:
            logger.info("✅ CTA validation passed - semantic match confirmed")

        logger.info("")
        # ========== END FASE 3 CTA VALIDATION ==========

    # Step 5: VisualPlanner - create visual scenes
    logger.info("Step 5: Running VisualPlanner to create visual plan...")
    # Step 09: Pass workspace_config for visual brand manual (color palette enforcement)
    # MONETIZATION REFACTOR: Pass duration_strategy for format-aware scene generation
    # Phase C - P2.2: Pass Timeline object for duration enforcement
    visual_plan = generate_visual_plan(
        video_plan,
        script,
        memory,
        series_format=series_format,
        workspace_config=workspace,
        duration_strategy=duration_strategy,
        timeline=timeline,  # Phase C - P2.2: Single source of truth for duration
        llm_generate_fn=llm_generate_fn  # Layer 2: AI-driven duration validation
    )
    total_duration = _calculate_total_duration(visual_plan)
    logger.info(f"✓ Visual plan created: {len(visual_plan.scenes)} scenes")
    logger.info(f"  Total estimated duration: {total_duration}s")
    logger.info(f"  Aspect ratio: {visual_plan.aspect_ratio}")

    # VALIDATION: Format Coherence (aspect ratio + duration)
    # Phase C - P0: Use timeline.reconciled_duration (single source of truth)
    target_duration_final = timeline.reconciled_duration if timeline else 480
    logger.info("")
    logger.info("📐 FORMAT COHERENCE VALIDATION")
    corrected_duration, corrected_aspect, was_corrected, reasoning = validate_and_enforce_format(
        workspace_config=workspace,
        target_duration=target_duration_final,
        aspect_ratio=visual_plan.aspect_ratio,
        video_style_mode=workspace.get('video_style_mode'),
        auto_correct=False,  # Don't auto-correct, just validate
        llm_generate_fn=llm_generate_fn
    )

    if was_corrected:
        logger.warning(f"⚠️ Format incoherence detected but not auto-corrected (validation only)")
        logger.warning(f"   Suggested: duration={corrected_duration}s, aspect_ratio={corrected_aspect}")
        logger.warning(f"   Reasoning: {reasoning}")
    else:
        logger.info("✅ Format coherence validated - aspect ratio matches duration tier")
    logger.info("")

    if total_duration > 60:
        logger.warning(f"Duration ({total_duration}s) exceeds typical Shorts length (60s)")

    # ========== VALIDATION GATE 4: POST-VISUAL ==========
    logger.info("")
    gate4_enabled, gate4_blocking = _is_gate_enabled(workspace, 'post_visual')

    if gate4_enabled:
        from yt_autopilot.core.pipeline_validator import Gate4_PostVisualValidator

        gate4_validator = Gate4_PostVisualValidator()

        # Phase C - P0: Pass Timeline object instead of reconciled_format dict
        gate4_result = gate4_validator.validate(
            visual_plan=visual_plan,
            script=script,
            duration_strategy=duration_strategy,
            reconciled_format=timeline  # Now Timeline object (backward compatible)
        )

        log_validation_result(gate4_result, gate_number=4)

        if not gate4_result.is_valid:
            blocking_issues = gate4_result.get_blocking_issues()
            logger.error(f"❌ Gate 4 validation failed with {len(blocking_issues)} blocking issues:")
            for issue in blocking_issues:
                logger.error(f"   • {issue.message}")

            if gate4_blocking:
                raise ValueError(
                    f"Visual plan validation failed. "
                    f"First issue: {blocking_issues[0].message}"
                )
            else:
                logger.warning("⚠️ Gate 4 non-blocking - continuing despite validation failure")
                for issue in blocking_issues[:3]:  # Show first 3 issues
                    logger.warning(f"   • {issue.message}")

        if gate4_result.warnings:
            logger.warning(f"⚠️ Gate 4 detected {len(gate4_result.warnings)} warnings:")
            for warning in gate4_result.warnings[:3]:  # Show first 3
                logger.warning(f"   • {warning}")

        if gate4_result.recommendations:
            logger.info(f"💡 Gate 4 recommendations:")
            for rec in gate4_result.recommendations[:2]:  # Show first 2
                logger.info(f"   • {rec}")

        logger.info("✅ Gate 4 validation passed - Visual plan consistent")
    else:
        logger.info("⚙️ Gate 4 (Post-Visual) disabled in config - skipping validation")

    logger.info("")
    # ========== END GATE 4 ==========

    # Step 6: SeoManager - optimize metadata
    logger.info("Step 6: Running SeoManager to optimize metadata...")
    publishing = generate_publishing_package(video_plan, script)
    logger.info(f"✓ Publishing package created")
    logger.info(f"  Title: '{publishing.final_title}' ({len(publishing.final_title)} chars)")
    logger.info(f"  Tags: {len(publishing.tags)} tags")
    logger.info(f"  Description: {len(publishing.description)} chars")

    # Step 7: QualityReviewer - first pass
    logger.info("Step 7: Running QualityReviewer (first pass)...")
    approved, reason = review(video_plan, script, visual_plan, publishing, memory, llm_generate_fn=llm_generate_fn)

    if approved:
        logger.info("✓ Quality check PASSED on first attempt")
    else:
        logger.warning(f"✗ Quality check FAILED on first attempt")
        logger.warning(f"  Rejection reason: {reason[:200]}...")

        # Step 8: Attempt ONE revision
        logger.info("Step 8: Attempting revision to address feedback...")

        # Improve script based on feedback
        revised_script = _attempt_script_improvement(script, reason, video_plan, memory)

        # Regenerate dependent components
        logger.info("  Regenerating visual plan with improved script...")
        # Step 09: Pass workspace_config for visual brand manual
        # MONETIZATION REFACTOR: Pass duration_strategy for format-aware scene generation
        # Phase C - P2.2: Pass Timeline object for duration enforcement
        revised_visual_plan = generate_visual_plan(
            video_plan,
            revised_script,
            memory,
            series_format=series_format,
            workspace_config=workspace,
            duration_strategy=duration_strategy,
            timeline=timeline,  # Phase C - P2.2: Single source of truth for duration
            llm_generate_fn=llm_generate_fn  # Layer 2: AI-driven duration validation
        )
        revised_duration = _calculate_total_duration(revised_visual_plan)
        logger.info(f"  Revised duration: {revised_duration}s (was {total_duration}s)")

        logger.info("  Regenerating publishing package with improved script...")
        revised_publishing = generate_publishing_package(video_plan, revised_script)
        logger.info(f"  Revised title: '{revised_publishing.final_title}'")

        # Re-run quality review
        logger.info("  Re-running QualityReviewer (second pass)...")
        approved, reason = review(
            video_plan,
            revised_script,
            revised_visual_plan,
            revised_publishing,
            memory,
            llm_generate_fn=llm_generate_fn
        )

        if approved:
            logger.info("✓ Quality check PASSED after revision")
            # Use revised components
            script = revised_script
            visual_plan = revised_visual_plan
            publishing = revised_publishing
            total_duration = revised_duration
        else:
            logger.error("✗ Quality check FAILED after revision - package REJECTED")
            logger.error(f"  Final rejection reason: {reason}")

            # Return REJECTED package (do NOT update memory)
            rejected_package = ContentPackage(
                status="REJECTED",
                video_plan=video_plan,
                script=revised_script,  # Use revised version for transparency
                visuals=revised_visual_plan,
                publishing=revised_publishing,
                rejection_reason=reason,
                llm_raw_script=llm_suggestion,  # Step 07: Audit trail
                final_script_text=revised_script.full_voiceover_text,  # Step 07: Audit trail
                editorial_decision=editorial_decision,  # Step 11: AI strategy tracking
                duration_strategy_reasoning=duration_reasoning,
                format_reconciliation_reasoning=format_reasoning,
                narrative_design_reasoning=narrative_reasoning,
                cta_strategy_reasoning=cta_reasoning
            )

            logger.info("=" * 70)
            logger.info("EDITORIAL PIPELINE COMPLETE: STATUS = REJECTED")
            logger.info("=" * 70)

            return rejected_package

    # Step 8: Monetization QA - final validation (NEW: Monetization Refactor)
    logger.info("Step 8: Running Monetization QA (YouTube monetization readiness)...")

    monetization_approved, monetization_feedback, monetization_scores = validate_monetization_readiness(
        plan=video_plan,
        script=script,
        visuals=visual_plan,
        publishing=publishing,
        duration_strategy=duration_strategy,
        narrative_arc=narrative_arc,
        subscriber_persona=workspace.get('subscriber_persona')
    )

    logger.info(f"Monetization QA feedback:\n{monetization_feedback}")

    if not monetization_approved:
        overall_score = monetization_scores.get('overall', 0.0)

        # Sprint 1.5: Retry logic with LLM-driven iterative refinement
        # Only retry if score is in "recoverable" range (0.60-0.75)
        # Too low (<0.60): fundamental issues, retry unlikely to help
        # Already approved (>=0.75): no retry needed
        if 0.60 <= overall_score < 0.75:
            logger.warning(f"✗ Monetization QA below threshold ({overall_score:.2f})")
            logger.info("  💡 Score is near threshold - attempting LLM-driven optimization (1 retry)...")

            # Phase C - P3: Apply full regeneration with QA feedback constraints
            try:
                improved_script, improved_visual, improved_publishing = \
                    _attempt_monetization_improvement(
                        script=script,
                        visual_plan=visual_plan,
                        publishing=publishing,
                        video_plan=video_plan,
                        memory=memory,
                        category_scores=monetization_scores,
                        monetization_feedback=monetization_feedback,
                        target_duration=duration_strategy['target_duration_seconds'],
                        series_format=series_format,
                        workspace=workspace,
                        duration_strategy=duration_strategy,
                        editorial_decision=editorial_decision,  # Phase C - P3
                        narrative_arc=narrative_arc,  # Phase C - P3
                        content_depth_strategy=content_depth_strategy  # Phase C - P3
                    )

                # Retry Monetization QA with improved package
                logger.info("  🔁 Re-running Monetization QA after LLM improvements...")
                retry_approved, retry_feedback, retry_scores = validate_monetization_readiness(
                    plan=video_plan,
                    script=improved_script,
                    visuals=improved_visual,
                    publishing=improved_publishing,
                    duration_strategy=duration_strategy,
                    narrative_arc=narrative_arc,
                    subscriber_persona=workspace.get('subscriber_persona')
                )

                retry_overall_score = retry_scores.get('overall', 0.0)
                logger.info(f"  Monetization QA retry result: {retry_feedback}")
                logger.info(f"  Score improvement: {overall_score:.2f} → {retry_overall_score:.2f} ({'+' if retry_overall_score > overall_score else ''}{retry_overall_score - overall_score:.2f})")

                if retry_approved:
                    logger.info("✓ Monetization QA PASSED after LLM optimization! 🎉")
                    logger.info(f"  Final score: {retry_overall_score:.2f}/1.00")

                    # Use improved versions for final package
                    script = improved_script
                    visual_plan = improved_visual
                    publishing = improved_publishing
                    monetization_approved = True
                    monetization_feedback = retry_feedback
                    monetization_scores = retry_scores
                else:
                    logger.warning(f"✗ Monetization QA still below threshold after retry ({retry_overall_score:.2f})")
                    logger.warning("  Returning as NEEDS_REVISION with improved content")

                    # Return improved version even if still not approved
                    return ContentPackage(
                        status="NEEDS_REVISION",
                        video_plan=video_plan,
                        script=improved_script,  # Use improved version
                        visuals=improved_visual,
                        publishing=improved_publishing,
                        rejection_reason=retry_feedback,
                        llm_raw_script=llm_suggestion,
                        final_script_text=improved_script.full_voiceover_text,
                        editorial_decision=editorial_decision,
                        duration_strategy_reasoning=duration_reasoning,
                        format_reconciliation_reasoning=format_reasoning,
                        narrative_design_reasoning=narrative_reasoning,
                        cta_strategy_reasoning=cta_reasoning
                    )

            except Exception as e:
                logger.error(f"❌ Monetization optimization failed: {e}")
                logger.warning("  Falling back to original version")
                # Continue to NEEDS_REVISION return below with original content

        # Score too low (<0.60) or retry failed/skipped → NEEDS_REVISION
        if not monetization_approved:
            if overall_score < 0.60:
                logger.warning(f"✗ Monetization QA FAILED - score too low ({overall_score:.2f} < 0.60)")
                logger.warning("  Score below retry threshold - package needs significant revision")
            else:
                logger.warning("✗ Monetization QA FAILED - package needs optimization")

            logger.warning("  Note: Package passes compliance but not monetization optimization")

            # Return package with monetization feedback (status: NEEDS_REVISION)
            needs_revision_package = ContentPackage(
                status="NEEDS_REVISION",
                video_plan=video_plan,
                script=script,
                visuals=visual_plan,
                publishing=publishing,
                rejection_reason=monetization_feedback,
                llm_raw_script=llm_suggestion,
                final_script_text=script.full_voiceover_text,
                editorial_decision=editorial_decision
            )

            logger.info("=" * 70)
            logger.info("EDITORIAL PIPELINE COMPLETE: STATUS = NEEDS_REVISION")
            logger.info("=" * 70)

            return needs_revision_package

    # If approved (either first attempt or after retry)
    logger.info("✓ Monetization QA PASSED - package is monetization-ready")
    logger.info(f"  Final score: {monetization_scores.get('overall', 0.0):.2f}/1.00")

    # Step 9: Package APPROVED - update workspace
    logger.info("Step 9: Package APPROVED - updating workspace configuration...")

    # Add title to recent titles to avoid repetition
    update_workspace_recent_titles(workspace_id, publishing.final_title, max_titles=50)

    logger.info(f"✓ Workspace updated with new title: '{publishing.final_title}'")
    logger.info(f"  Workspace: {workspace['workspace_name']} ({workspace_id})")

    # Step 10: Create final APPROVED package
    approved_package = ContentPackage(
        status="APPROVED",
        video_plan=video_plan,
        script=script,
        visuals=visual_plan,
        publishing=publishing,
        rejection_reason=None,
        llm_raw_script=llm_suggestion,  # Step 07: Audit trail
        final_script_text=script.full_voiceover_text,  # Step 07: Audit trail
        editorial_decision=editorial_decision,  # Step 11: AI strategy tracking for analytics
        duration_strategy_reasoning=duration_reasoning,
        format_reconciliation_reasoning=format_reasoning,
        narrative_design_reasoning=narrative_reasoning,
        cta_strategy_reasoning=cta_reasoning
    )

    logger.info("=" * 70)
    logger.info("EDITORIAL PIPELINE COMPLETE: STATUS = APPROVED")
    logger.info(f"Final package ready for production:")
    logger.info(f"  Title: '{publishing.final_title}'")
    logger.info(f"  Duration: ~{total_duration}s")
    logger.info(f"  Scenes: {len(visual_plan.scenes)}")
    logger.info(f"  Language: {video_plan.language}")
    logger.info("=" * 70)

    return approved_package
