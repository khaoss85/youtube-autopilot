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
    ReadyForFactory,
    VideoPlan,
    VideoScript,
    VisualPlan,
    PublishingPackage
)
from yt_autopilot.core.workspace_manager import (
    get_active_workspace,
    load_workspace_config,
    save_workspace_config,
    update_workspace_recent_titles
)
from yt_autopilot.core.logger import logger

# Import agents
from yt_autopilot.agents.trend_hunter import generate_video_plan
from yt_autopilot.agents.script_writer import write_script
from yt_autopilot.agents.visual_planner import generate_visual_plan
from yt_autopilot.agents.seo_manager import generate_publishing_package
from yt_autopilot.agents.quality_reviewer import review

# Import services (Step 06-fullrun: LLM integration)
from yt_autopilot.services.llm_router import generate_text

# Phase B: LLM-powered trend curation
from yt_autopilot.services.llm_trend_curator import curate_trends_with_llm

# Step 08: Real trend fetching
from yt_autopilot.services.trend_source import fetch_trends

# Step 07.5: Series format engine
from yt_autopilot.core import series_manager


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

    # Create improved version based on common rejection patterns
    improved_hook = script.hook
    improved_bullets = script.bullets.copy()
    improved_cta = script.outro_cta

    # If hook is weak, make it stronger
    if "hook" in reason.lower() or "attention" in reason.lower():
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


def build_video_package(
    workspace_id: Optional[str] = None,
    use_real_trends: bool = False,
    use_llm_curation: bool = False
) -> ReadyForFactory:
    """
    Orchestrates the full editorial pipeline to produce a ReadyForFactory package.

    This is the main orchestrator for the editorial brain. It coordinates all
    AI agents in sequence, handles quality review with one retry attempt,
    and updates workspace configuration when content is approved.

    Workflow:
        1. Load workspace configuration (replaces channel memory)
        2. Fetch trending topics (Phase A quality filtering applied)
        2.5. [OPTIONAL] LLM curation (Phase B: select top 10 from ~25 trends)
        3. TrendHunter selects best topic → VideoPlan
        4. ScriptWriter generates script → VideoScript
        5. VisualPlanner creates scenes → VisualPlan
        6. SeoManager optimizes metadata → PublishingPackage
        7. QualityReviewer checks compliance → APPROVED/REJECTED
        8. If REJECTED: attempt ONE revision and re-check
        9. If APPROVED: update workspace with new title
        10. Return ReadyForFactory package

    Args:
        workspace_id: Workspace ID to use (if None, uses active workspace)
        use_real_trends: If True, fetch real trends from APIs; if False, use mocks
        use_llm_curation: If True, use LLM to curate top 10 trends (Phase B); if False, use Phase A filtering only

    Returns:
        ReadyForFactory object with status "APPROVED" or "REJECTED"

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
    logger.info(f"  Brand tone: {workspace.get('brand_tone', 'Not set')[:60]}...")

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
                llm_generate_fn=generate_text,
                max_trends_to_evaluate=min(30, len(trends)),
                top_n=10
            )
            logger.info(f"✓ LLM curation complete: {len(trends)} → {len(curated_trends)} trends")
            trends = curated_trends
        except Exception as e:
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
    logger.info("  Phase A source weighting: Reddit 3x > HN 2x > YouTube 1x")
    video_plan = generate_video_plan(trends, memory)
    logger.info(f"✓ Selected trend: '{video_plan.working_title}'")
    logger.info(f"  Target audience: {video_plan.target_audience}")
    logger.info(f"  Compliance notes: {len(video_plan.compliance_notes)} checks")

    # Step 3.5: Detect series format (Step 07.5: Format engine)
    logger.info("Step 3.5: Detecting series format...")
    serie_id = series_manager.detect_serie(
        video_plan.working_title,
        video_plan.strategic_angle
    )
    series_format = series_manager.load_format(serie_id)
    logger.info(f"✓ Series format: {series_format.name} ({serie_id})")
    logger.info(f"  Structure: {len(series_format.segments)} segments")

    # Update video plan with series_id
    video_plan.series_id = serie_id

    # Step 4: ScriptWriter - generate script (NEW: with LLM integration)
    logger.info("Step 4: Running ScriptWriter to generate script...")

    # NEW (Step 06-fullrun): Call LLM for creative script suggestion
    logger.info("  Step 4a: Calling LLM for creative script generation...")

    brand_tone = workspace.get('brand_tone', 'Direct, positive, educational')

    llm_context = f"""
Topic: {video_plan.working_title}
Strategic Angle: {video_plan.strategic_angle}
Target Audience: {video_plan.target_audience}
Language: {video_plan.language}
Format: YouTube Shorts (vertical 9:16, max 60 seconds)
Brand Tone: {brand_tone}
    """.strip()

    llm_task = """
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
- <punto chiave 1>
- <punto chiave 2>
- <punto chiave 3>
- <punto chiave 4>

CTA:
<call-to-action breve e non invasiva>

VOICEOVER:
<testo completo del voiceover da leggere ad alta voce, 15-60 secondi, include hook + bullets + CTA in forma narrativa>

IMPORTANTE - STILE CREATOR (Step 07.2):
- Il VOICEOVER deve essere il testo finale parlato, NON una lista di punti
- Tono ENERGICO e COINVOLGENTE (non monotono o da documentario)
- Frasi BREVI e INCISIVE (max 10-12 parole per frase)
- Usa espressioni colloquiali italiane: "Ascolta", "Ti faccio vedere", "Guarda qui", "Ecco cosa devi sapere"
- Parla in SECONDA PERSONA SINGOLARE ("tu"), stile diretto e personale
- HOOK POTENTE nei primi 2 secondi che cattura l'attenzione
- Flow naturale come se stessi parlando a un amico
- Energetico ma non urlato, coinvolgente ma non artificiale
    """.strip()

    llm_suggestion = generate_text(
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
    script = write_script(video_plan, memory, llm_suggestion=llm_suggestion, series_format=series_format)

    logger.info(f"✓ Script generated: {len(script.bullets)} content points")
    logger.info(f"  Hook: '{script.hook[:60]}...'")
    logger.info(f"  Voiceover length: {len(script.full_voiceover_text)} chars")

    # Step 5: VisualPlanner - create visual scenes
    logger.info("Step 5: Running VisualPlanner to create visual plan...")
    visual_plan = generate_visual_plan(video_plan, script, memory, series_format=series_format)
    total_duration = _calculate_total_duration(visual_plan)
    logger.info(f"✓ Visual plan created: {len(visual_plan.scenes)} scenes")
    logger.info(f"  Total estimated duration: {total_duration}s")
    logger.info(f"  Aspect ratio: {visual_plan.aspect_ratio}")

    if total_duration > 60:
        logger.warning(f"Duration ({total_duration}s) exceeds typical Shorts length (60s)")

    # Step 6: SeoManager - optimize metadata
    logger.info("Step 6: Running SeoManager to optimize metadata...")
    publishing = generate_publishing_package(video_plan, script)
    logger.info(f"✓ Publishing package created")
    logger.info(f"  Title: '{publishing.final_title}' ({len(publishing.final_title)} chars)")
    logger.info(f"  Tags: {len(publishing.tags)} tags")
    logger.info(f"  Description: {len(publishing.description)} chars")

    # Step 7: QualityReviewer - first pass
    logger.info("Step 7: Running QualityReviewer (first pass)...")
    approved, reason = review(video_plan, script, visual_plan, publishing, memory)

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
        revised_visual_plan = generate_visual_plan(video_plan, revised_script, memory, series_format=series_format)
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
            memory
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
            rejected_package = ReadyForFactory(
                status="REJECTED",
                video_plan=video_plan,
                script=revised_script,  # Use revised version for transparency
                visuals=revised_visual_plan,
                publishing=revised_publishing,
                rejection_reason=reason,
                llm_raw_script=llm_suggestion,  # Step 07: Audit trail
                final_script_text=revised_script.full_voiceover_text  # Step 07: Audit trail
            )

            logger.info("=" * 70)
            logger.info("EDITORIAL PIPELINE COMPLETE: STATUS = REJECTED")
            logger.info("=" * 70)

            return rejected_package

    # Step 9: Package APPROVED - update workspace
    logger.info("Step 9: Package APPROVED - updating workspace configuration...")

    # Add title to recent titles to avoid repetition
    update_workspace_recent_titles(workspace_id, publishing.final_title, max_titles=50)

    logger.info(f"✓ Workspace updated with new title: '{publishing.final_title}'")
    logger.info(f"  Workspace: {workspace['workspace_name']} ({workspace_id})")

    # Step 10: Create final APPROVED package
    approved_package = ReadyForFactory(
        status="APPROVED",
        video_plan=video_plan,
        script=script,
        visuals=visual_plan,
        publishing=publishing,
        rejection_reason=None,
        llm_raw_script=llm_suggestion,  # Step 07: Audit trail
        final_script_text=script.full_voiceover_text  # Step 07: Audit trail
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
