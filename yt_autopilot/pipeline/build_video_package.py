"""
Editorial Pipeline Orchestrator: Coordinates AI agents to produce video packages.

This module orchestrates the complete editorial workflow from trend selection
to quality-approved content packages, managing the multi-agent system and
memory updates.

NEW (Step 06-fullrun): Integrates real LLM calls via llm_router to enhance
script generation with AI creativity while maintaining safety rules.
"""

from typing import List, Dict
from yt_autopilot.core.schemas import (
    TrendCandidate,
    ReadyForFactory,
    VideoPlan,
    VideoScript,
    VisualPlan,
    PublishingPackage
)
from yt_autopilot.core.memory_store import (
    load_memory,
    save_memory,
    append_recent_title,
    get_brand_tone
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
        memory: Channel memory

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


def build_video_package() -> ReadyForFactory:
    """
    Orchestrates the full editorial pipeline to produce a ReadyForFactory package.

    This is the main orchestrator for the editorial brain. It coordinates all
    AI agents in sequence, handles quality review with one retry attempt,
    and updates channel memory when content is approved.

    Workflow:
        1. Load channel memory
        2. Get trending topics (currently mocked)
        3. TrendHunter selects best topic → VideoPlan
        4. ScriptWriter generates script → VideoScript
        5. VisualPlanner creates scenes → VisualPlan
        6. SeoManager optimizes metadata → PublishingPackage
        7. QualityReviewer checks compliance → APPROVED/REJECTED
        8. If REJECTED: attempt ONE revision and re-check
        9. If APPROVED: update memory with new title
        10. Return ReadyForFactory package

    Returns:
        ReadyForFactory object with status "APPROVED" or "REJECTED"

    Notes:
        - Does NOT call external APIs (Veo, YouTube, etc.)
        - Does NOT generate actual video files
        - Does NOT upload anything
        - Only coordinates editorial decisions and memory management
    """
    logger.info("=" * 70)
    logger.info("STARTING EDITORIAL PIPELINE: build_video_package()")
    logger.info("=" * 70)

    # Step 1: Load channel memory
    logger.info("Step 1: Loading channel memory...")
    memory = load_memory()
    logger.info(f"Memory loaded successfully (recent titles: {len(memory.get('recent_titles', []))})")

    # Step 2: Get trending topics (mocked for now)
    logger.info("Step 2: Collecting trending topics...")
    trends = _get_mock_trends()
    logger.info(f"Collected {len(trends)} trend candidates (source: mock)")

    # Step 3: TrendHunter - select best topic
    logger.info("Step 3: Running TrendHunter to select best topic...")
    video_plan = generate_video_plan(trends, memory)
    logger.info(f"✓ Selected trend: '{video_plan.working_title}'")
    logger.info(f"  Target audience: {video_plan.target_audience}")
    logger.info(f"  Compliance notes: {len(video_plan.compliance_notes)} checks")

    # Step 4: ScriptWriter - generate script (NEW: with LLM integration)
    logger.info("Step 4: Running ScriptWriter to generate script...")

    # NEW (Step 06-fullrun): Call LLM for creative script suggestion
    logger.info("  Step 4a: Calling LLM for creative script generation...")

    brand_tone = get_brand_tone(memory)

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
<testo completo del voiceover da leggere ad alta voce, 15-60 secondi, tono educativo e diretto, flow naturale, include hook + bullets + CTA in forma narrativa>

IMPORTANTE: Il VOICEOVER deve essere il testo finale parlato, non una lista di punti.
Deve scorrere naturalmente come una narrazione continua.
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
    script = write_script(video_plan, memory, llm_suggestion=llm_suggestion)

    logger.info(f"✓ Script generated: {len(script.bullets)} content points")
    logger.info(f"  Hook: '{script.hook[:60]}...'")
    logger.info(f"  Voiceover length: {len(script.full_voiceover_text)} chars")

    # Step 5: VisualPlanner - create visual scenes
    logger.info("Step 5: Running VisualPlanner to create visual plan...")
    visual_plan = generate_visual_plan(video_plan, script, memory)
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
        revised_visual_plan = generate_visual_plan(video_plan, revised_script, memory)
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

    # Step 9: Package APPROVED - update memory
    logger.info("Step 9: Package APPROVED - updating channel memory...")

    # Add title to recent titles to avoid repetition
    append_recent_title(memory, publishing.final_title)
    save_memory(memory)

    logger.info(f"✓ Memory updated with new title: '{publishing.final_title}'")
    logger.info(f"  Total recent titles in memory: {len(memory['recent_titles'])}")

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
