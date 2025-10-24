"""
VisualPlanner Agent: Creates scene-by-scene visual plans for video generation.

This agent transforms scripts into detailed visual plans with prompts
for Veo video generation API, optimized for YouTube Shorts vertical format.
"""

from typing import Dict, List, Tuple
from yt_autopilot.core.schemas import VideoPlan, VideoScript, VisualPlan, VisualScene
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
    memory: Dict
) -> VisualPlan:
    """
    Generates a complete visual plan with scene-by-scene prompts for Veo.

    This is the entry point for the VisualPlanner agent. It:
    - Divides the script into logical visual scenes
    - Creates Veo-compatible generation prompts for each scene
    - Estimates duration for each scene
    - Applies channel's visual style consistently

    Optimized for YouTube Shorts (vertical 9:16 format, ~60 seconds total).

    Args:
        plan: Video plan with topic and context
        script: Complete video script
        memory: Channel memory dict containing visual_style

    Returns:
        VisualPlan with scene list and style notes

    Raises:
        ValueError: If script is invalid
    """
    if not script.full_voiceover_text:
        raise ValueError("Cannot generate visual plan: script has no voiceover text")

    logger.info(f"VisualPlanner creating scenes for: '{plan.working_title}'")

    # Load visual style from memory
    visual_style = get_visual_style(memory)

    # Divide script into scenes
    segments = _create_scene_segments(script)

    # Create VisualScene for each segment
    scenes: List[VisualScene] = []
    for scene_id, (segment_name, segment_text) in enumerate(segments, start=1):
        # Generate Veo prompt
        veo_prompt = _generate_veo_prompt(segment_name, segment_text, plan, visual_style)

        # Estimate duration
        duration = _estimate_duration_from_text(segment_text)

        # Create scene
        scene = VisualScene(
            scene_id=scene_id,
            prompt_for_veo=veo_prompt,
            est_duration_seconds=duration
        )

        scenes.append(scene)
        logger.debug(f"Scene {scene_id}: {duration}s - {segment_name}")

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
