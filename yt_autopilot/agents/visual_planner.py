"""
VisualPlanner Agent: Creates scene-by-scene visual plans for video generation.

This agent transforms scripts into detailed visual plans with prompts
for Veo video generation API, optimized for YouTube Shorts vertical format.

==============================================================================
LLM Integration Strategy (Step 06-pre)
==============================================================================

CURRENT: Deterministic visual scene breakdown (rule-based)
FUTURE: LLM-enhanced Veo prompts via services/llm_router

INTEGRATION APPROACH:
- Pipeline calls llm_router to enhance Veo prompts for each scene
- LLM generates creative, Veo-optimized visual descriptions
- Agent combines LLM prompts + brand visual style
- Architecture maintained: no direct import from services/

Example:
    veo_prompt = generate_text(
        role="visual_planner",
        task="Create Veo prompt for scene showing tech innovation",
        context=f"Script line: {bullet}, Visual style: {visual_style}",
        style_hints={"aspect_ratio": "9:16", "format": "YouTube Shorts"}
    )

==============================================================================
Step 07.5: Format Engine Evolution
==============================================================================

NEW: Visual format engine with intro/outro support
- Accepts SeriesFormat template for structured visual planning
- Adds intro/outro scenes to visual plan
- Tags VisualScene with segment_type from script
- Maintains backward compatibility (series_format=None → legacy mode)

==============================================================================
"""

from typing import Dict, List, Tuple, Optional
from yt_autopilot.core.schemas import VideoPlan, VideoScript, VisualPlan, VisualScene, SceneVoiceover, SeriesFormat
from yt_autopilot.core.memory_store import get_visual_style
from yt_autopilot.core.logger import logger


def _estimate_duration_from_text(text: str) -> int:
    """
    Estimates speaking duration in seconds based on text length.

    Uses average speaking rate of ~150 words per minute (2.5 words/sec).

    Args:
        text: Text to estimate duration for

    Returns:
        Estimated duration in seconds (minimum 3 seconds)
    """
    word_count = len(text.split())
    duration = max(3, int(word_count / 2.5))  # 2.5 words/sec average speaking rate
    return duration


def _create_scene_segments(script: VideoScript) -> List[Tuple[str, str]]:
    """
    Divides script into logical scene segments.

    Args:
        script: Video script with hook, bullets, outro

    Returns:
        List of (segment_name, text) tuples
    """
    segments = []

    # Hook scene (opening attention grabber)
    segments.append(("hook", script.hook))

    # Content scenes (one per bullet or grouped)
    # For Shorts, we want concise scenes (max 5-6 total)
    if len(script.bullets) <= 3:
        # One scene per bullet if few bullets
        for i, bullet in enumerate(script.bullets):
            segments.append((f"content_{i+1}", bullet))
    else:
        # Group bullets into 2-3 scenes if many bullets
        mid_point = len(script.bullets) // 2
        segments.append(("content_1", " ".join(script.bullets[:mid_point])))
        segments.append(("content_2", " ".join(script.bullets[mid_point:])))

    # Outro scene (CTA)
    segments.append(("outro", script.outro_cta))

    return segments


def _generate_veo_prompt(
    segment_name: str,
    segment_text: str,
    plan: VideoPlan,
    visual_style: str
) -> str:
    """
    Generates a descriptive prompt for Veo video generation API.

    Args:
        segment_name: Name of the segment (hook, content_1, etc.)
        segment_text: Text content of the segment
        plan: Video plan for context
        visual_style: Channel's visual style from memory

    Returns:
        Veo-compatible prompt string
    """
    # Base style elements from memory
    # Expected: "Ritmo alto, colori caldi, testo grande in sovrimpressione stile Shorts verticali"

    # Extract key visual elements
    has_warm_colors = "caldi" in visual_style.lower()
    has_text_overlay = "testo" in visual_style.lower()
    is_vertical = "verticali" in visual_style.lower() or "9:16" in visual_style.lower()

    # Build prompt based on segment type
    if segment_name == "hook":
        # Hook: attention-grabbing, dynamic
        prompt = (
            f"Dynamic vertical video shot, {plan.working_title} theme. "
            f"Fast-paced camera movement, {'warm vibrant colors' if has_warm_colors else 'bold colors'}, "
            f"modern aesthetic. High energy opening sequence. "
            f"{'Large text overlay visible' if has_text_overlay else 'Clean visual focus'}. "
            f"Cinematic lighting, professional quality."
        )

    elif segment_name.startswith("content"):
        # Content: informative, clear
        prompt = (
            f"Engaging vertical video, explaining {plan.working_title}. "
            f"Clean composition, {'warm color palette' if has_warm_colors else 'professional colors'}, "
            f"informative visual elements. Smooth camera transitions. "
            f"{'Key text overlays for emphasis' if has_text_overlay else 'Visual clarity'}. "
            f"Modern production style."
        )

    elif segment_name == "outro":
        # Outro: call-to-action, memorable
        prompt = (
            f"Closing vertical video shot, {plan.working_title} conclusion. "
            f"Positive and inviting atmosphere, {'warm friendly colors' if has_warm_colors else 'bright colors'}, "
            f"call-to-action visual. "
            f"{'Large CTA text overlay' if has_text_overlay else 'Engaging final frame'}. "
            f"Professional quality finish."
        )

    else:
        # Generic fallback
        prompt = (
            f"Professional vertical video, {plan.working_title} content. "
            f"{'Warm color scheme' if has_warm_colors else 'Dynamic colors'}, "
            f"high production quality, engaging visuals."
        )

    # Add vertical format specification
    if is_vertical:
        prompt += " Vertical 9:16 aspect ratio optimized for mobile viewing."

    return prompt


def generate_visual_plan(
    plan: VideoPlan,
    script: VideoScript,
    memory: Dict,
    series_format: Optional[SeriesFormat] = None
) -> VisualPlan:
    """
    Generates a complete visual plan with scene-by-scene prompts for Veo.

    This is the entry point for the VisualPlanner agent. It:
    - Syncs visual scenes with script's scene_voiceover_map (Step 07.3)
    - Creates Veo-compatible generation prompts for each scene
    - Embeds voiceover text into each scene for precise sync
    - Applies channel's visual style consistently

    Step 07.3: Now uses script.scene_voiceover_map for precise audio/visual sync.
    Falls back to legacy scene segmentation if scene_voiceover_map is empty.

    Step 07.5: Format engine - adds intro/outro scenes and tags with segment_type.
    If series_format is provided, creates intro/outro scenes from template.

    Optimized for YouTube Shorts (vertical 9:16 format, ~60 seconds total).

    Args:
        plan: Video plan with topic and context
        script: Complete video script (with scene_voiceover_map in Step 07.3+)
        memory: Channel memory dict containing visual_style
        series_format: Optional series format template for intro/outro (Step 07.5)

    Returns:
        VisualPlan with scene list and style notes (includes intro/outro if series_format)

    Raises:
        ValueError: If script is invalid
    """
    if not script.full_voiceover_text:
        raise ValueError("Cannot generate visual plan: script has no voiceover text")

    logger.info(f"VisualPlanner creating scenes for: '{plan.working_title}'")

    if series_format:
        logger.info(f"  Format engine mode: {series_format.name} ({series_format.serie_id})")

    # Load visual style from memory
    visual_style = get_visual_style(memory)

    # Step 07.3/07.5: Use scene_voiceover_map if available (new), else fall back to legacy segmentation
    scenes: List[VisualScene] = []

    # Step 07.5: Add intro scene if series_format is provided
    if series_format:
        intro_scene = VisualScene(
            scene_id=0,  # Intro is scene 0
            prompt_for_veo=series_format.intro_veo_prompt,
            est_duration_seconds=series_format.intro_duration_seconds,
            voiceover_text="",  # No voiceover for intro
            segment_type="intro"
        )
        scenes.append(intro_scene)
        logger.info(f"  Added intro scene: {series_format.intro_duration_seconds}s")

    if script.scene_voiceover_map and len(script.scene_voiceover_map) > 0:
        # NEW (Step 07.3): Use scene_voiceover_map for precise sync
        logger.info(f"  Using scene_voiceover_map ({len(script.scene_voiceover_map)} content scenes)")

        for scene_vo in script.scene_voiceover_map:
            # Step 07.5: Use segment_type from script if available (set by ScriptWriter)
            # Otherwise, determine based on scene position (legacy)
            if hasattr(scene_vo, 'segment_type') and scene_vo.segment_type:
                segment_name = scene_vo.segment_type
            elif scene_vo.scene_id == 1:
                segment_name = "hook"
            elif scene_vo.scene_id == len(script.scene_voiceover_map):
                segment_name = "cta"
            else:
                segment_name = f"content_{scene_vo.scene_id - 1}"

            # Generate Veo prompt for this scene
            veo_prompt = _generate_veo_prompt(
                segment_name,
                scene_vo.voiceover_text,
                plan,
                visual_style
            )

            # Create VisualScene with embedded voiceover text (Step 07.3)
            # and segment_type (Step 07.5)
            scene = VisualScene(
                scene_id=scene_vo.scene_id,
                prompt_for_veo=veo_prompt,
                est_duration_seconds=scene_vo.est_duration_seconds,
                voiceover_text=scene_vo.voiceover_text,  # Sync with script!
                segment_type=segment_name  # Step 07.5: Tag with segment type
            )

            scenes.append(scene)
            logger.debug(
                f"Scene {scene_vo.scene_id}: {scene_vo.est_duration_seconds}s - "
                f"{segment_name} - '{scene_vo.voiceover_text[:40]}...'"
            )

    else:
        # LEGACY: Fall back to old segmentation (for backward compatibility)
        logger.warning(
            "  scene_voiceover_map is empty - using legacy scene segmentation. "
            "Consider regenerating script with Step 07.3+ for better sync."
        )

        segments = _create_scene_segments(script)

        for scene_id, (segment_name, segment_text) in enumerate(segments, start=1):
            # Generate Veo prompt
            veo_prompt = _generate_veo_prompt(segment_name, segment_text, plan, visual_style)

            # Estimate duration
            duration = _estimate_duration_from_text(segment_text)

            # Create scene (legacy mode with segment_type for Step 07.5 compatibility)
            scene = VisualScene(
                scene_id=scene_id,
                prompt_for_veo=veo_prompt,
                est_duration_seconds=duration,
                voiceover_text=segment_text,  # Use segment text as fallback
                segment_type=segment_name  # Step 07.5: Tag with segment type
            )

            scenes.append(scene)
            logger.debug(f"Scene {scene_id}: {duration}s - {segment_name}")

    # Step 07.5: Add outro scene if series_format is provided
    if series_format:
        # Outro scene ID is after all content scenes
        outro_scene_id = max(s.scene_id for s in scenes) + 1 if scenes else 1

        outro_scene = VisualScene(
            scene_id=outro_scene_id,
            prompt_for_veo=series_format.outro_veo_prompt,
            est_duration_seconds=series_format.outro_duration_seconds,
            voiceover_text="",  # No voiceover for outro
            segment_type="outro"
        )
        scenes.append(outro_scene)
        logger.info(f"  Added outro scene: {series_format.outro_duration_seconds}s")

    # Calculate total duration
    total_duration = sum(scene.est_duration_seconds for scene in scenes)

    # Create VisualPlan
    visual_plan = VisualPlan(
        aspect_ratio="9:16",  # YouTube Shorts vertical format
        style_notes=visual_style,
        scenes=scenes
    )

    logger.info(
        f"Generated VisualPlan: {len(scenes)} scenes, "
        f"total ~{total_duration}s duration"
    )

    # Warn if too long for Shorts
    if total_duration > 60:
        logger.warning(
            f"Visual plan duration ({total_duration}s) exceeds typical Shorts length (60s). "
            "Consider condensing script."
        )

    return visual_plan
