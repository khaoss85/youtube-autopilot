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
import random
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


def _select_visual_context(series_format: Optional[SeriesFormat], visual_contexts_config: Dict) -> Optional[Dict]:
    """
    Selects a visual context for content scenes based on format and frequency.

    Step 09: Visual Contexts - recurring scenarios boost retention through pattern recognition.

    Args:
        series_format: Series format template (to check format type)
        visual_contexts_config: Visual contexts configuration from workspace

    Returns:
        Selected context dict with context_id, name, veo_prompt_prefix, or None if no match
    """
    if not visual_contexts_config or not visual_contexts_config.get('enabled'):
        return None

    contexts = visual_contexts_config.get('contexts', [])
    if not contexts:
        return None

    # Get format type
    format_type = series_format.serie_id if series_format else 'generic'

    # Filter contexts by applicable_formats
    applicable_contexts = [
        ctx for ctx in contexts
        if format_type in ctx.get('applicable_formats', [])
    ]

    if not applicable_contexts:
        return None

    # Weighted random selection based on use_frequency
    weights = [ctx.get('use_frequency', 0.5) for ctx in applicable_contexts]
    selected_context = random.choices(applicable_contexts, weights=weights, k=1)[0]

    logger.info(f"  Visual context selected: {selected_context['name']} (frequency: {selected_context.get('use_frequency')*100:.0f}%)")

    return selected_context


def _build_character_description(character_profile: Dict) -> str:
    """
    Builds a persistent identity anchor from character profile.

    Step 09.5: Character Consistency - creates concise description for Veo/Sora
    to maintain same character across all scenes.

    Args:
        character_profile: Primary character profile from workspace config

    Returns:
        Persistent identity anchor string (e.g., "Same athletic male trainer with short dark hair...")

    Example:
        >>> profile = {
        ...     "persona": "Athletic male fitness trainer, early 30s",
        ...     "physical_traits": "Short dark brown hair, athletic build",
        ...     "typical_clothing": "Black athletic tank top"
        ... }
        >>> desc = _build_character_description(profile)
        >>> "Same athletic male" in desc
        True
    """
    # Extract key elements
    persona = character_profile.get('persona', '')
    physical_traits = character_profile.get('physical_traits', '')
    clothing = character_profile.get('typical_clothing', '')

    # Build concise identity anchor (20-30 words optimal)
    # Format: "Same [persona descriptor], [physical traits], wearing [clothing]"
    parts = []

    if persona:
        # Extract key descriptor from persona (e.g., "Athletic male fitness trainer, early 30s" → "athletic male trainer")
        persona_parts = persona.lower().split(',')
        persona_descriptor = persona_parts[0].strip() if persona_parts else persona.lower().strip()
        parts.append(f"Same {persona_descriptor}")

    if physical_traits:
        parts.append(physical_traits.lower())

    if clothing:
        parts.append(f"wearing {clothing.lower()}")

    description = ", ".join(parts) if parts else "Same person"

    return description


def _select_ai_visual_format(
    script: VideoScript,
    plan: VideoPlan,
    ai_style_preferences: Dict,
    vertical_id: str
) -> Tuple[str, str]:
    """
    Uses LLM to select optimal visual format for faceless video based on content.

    Step 09.7: AI-driven format selection with consistency across all scenes.
    Called ONCE per video to ensure format coherence.

    Args:
        script: Complete video script with hook, bullets, CTA
        plan: Video plan with title and strategic angle
        ai_style_preferences: AI preferences from workspace config
        vertical_id: Content vertical (e.g., 'finance', 'tech_ai', 'gaming')

    Returns:
        Tuple of (format_id, rationale)
        format_id: Selected format (e.g., 'whiteboard_animation', 'kinetic_typography')
        rationale: Why this format was chosen

    Supported Formats:
        - whiteboard_animation: Hand-drawn style explanations
        - kinetic_typography: Animated text with motion graphics
        - animated_infographics: Data visualization and charts
        - cinematic_broll: Professional stock footage
        - podcast_style: Audio-focused with waveforms/minimal visuals
        - stop_motion: Stop-motion animation aesthetic
        - code_visualization: Code snippets and terminal displays (tech verticals)

    Example:
        >>> format_id, rationale = _select_ai_visual_format(script, plan, prefs, "finance")
        >>> print(format_id)
        'animated_infographics'
        >>> print(rationale)
        'Financial data explanation benefits from chart animations and data viz'
    """
    from yt_autopilot.services.llm_router import generate_text

    logger.info("  🎨 AI Visual Format Selector: Analyzing script...")

    # Build context for LLM
    vertical_aesthetic = ai_style_preferences.get('vertical_aesthetic', 'professional')
    brand_vibe = ai_style_preferences.get('brand_vibe', 'engaging and informative')
    preferred_styles = ai_style_preferences.get('preferred_styles', [])

    # Format preferences hint
    preferences_hint = ""
    if preferred_styles:
        preferences_hint = f"\nPreferred styles for this channel: {', '.join(preferred_styles)}"

    task = """Select the SINGLE BEST visual format for this entire faceless video.
Choose ONE format that will be used consistently across ALL scenes.

Available formats:
- whiteboard_animation: Hand-drawn explanations (great for education, step-by-step)
- kinetic_typography: Animated text with motion graphics (great for quotes, stats, energy)
- animated_infographics: Data visualization and animated charts (great for numbers, trends)
- cinematic_broll: Professional stock footage (great for storytelling, aspirational)
- podcast_style: Audio-focused with waveforms and minimal visuals (great for commentary)
- stop_motion: Stop-motion animation aesthetic (great for creative, unique content)
- code_visualization: Code snippets and terminal displays (tech/programming only)

Return your response in this EXACT format:
FORMAT: <format_id>
RATIONALE: <one sentence explanation>"""

    context = f"""Video Title: {plan.working_title}
Strategic Angle: {plan.strategic_angle}
Vertical: {vertical_id}
Aesthetic: {vertical_aesthetic}
Brand Vibe: {brand_vibe}{preferences_hint}

Script Hook: {script.hook}
Main Points: {', '.join(script.bullets[:3])}
CTA: {script.outro_cta}"""

    style_hints = {
        "output_format": "FORMAT: <id>\\nRATIONALE: <explanation>",
        "constraint": "Choose ONE format for the entire video, not different formats per scene"
    }

    try:
        llm_response = generate_text(
            role="visual_format_selector",
            task=task,
            context=context,
            style_hints=style_hints
        )

        # Parse LLM response
        format_id = "cinematic_broll"  # default fallback
        rationale = "Professional stock footage for broad appeal"

        lines = llm_response.strip().split('\n')
        for line in lines:
            if line.startswith('FORMAT:'):
                format_id = line.replace('FORMAT:', '').strip()
            elif line.startswith('RATIONALE:'):
                rationale = line.replace('RATIONALE:', '').strip()

        # Validate format_id
        valid_formats = [
            'whiteboard_animation', 'kinetic_typography', 'animated_infographics',
            'cinematic_broll', 'podcast_style', 'stop_motion', 'code_visualization'
        ]
        if format_id not in valid_formats:
            logger.warning(f"  ⚠️  Invalid format '{format_id}', falling back to cinematic_broll")
            format_id = "cinematic_broll"
            rationale = "Fallback to professional stock footage"

        logger.info(f"  ✓ AI selected format: {format_id}")
        logger.info(f"    Rationale: {rationale}")

        return format_id, rationale

    except Exception as e:
        logger.error(f"  ✗ AI format selection failed: {e}, using fallback")
        return "cinematic_broll", "Fallback due to AI selection error"


# ==============================================================================
# CINEMATIC PROMPT ENGINE (Sora 2 Best Practices)
# ==============================================================================

def _get_shot_progression(series_format_name: str) -> List[Dict]:
    """
    Returns shot type progression for a series format.

    Sora 2 Best Practice: Alternate wide → medium → close for engagement.
    Each shot type serves a specific purpose in storytelling.

    Args:
        series_format_name: Name of series format (tutorial, how_to, news_flash)

    Returns:
        List of shot specifications with type, lens, and purpose
    """
    SHOT_PROGRESSIONS = {
        "tutorial": [
            {"shot": "wide", "lens": "24mm", "purpose": "establish context"},
            {"shot": "medium", "lens": "50mm", "purpose": "hook attention"},
            {"shot": "close", "lens": "85mm", "purpose": "detail focus"},
            {"shot": "medium", "lens": "50mm", "purpose": "process show"},
            {"shot": "close", "lens": "85mm", "purpose": "key point"},
            {"shot": "wide", "lens": "35mm", "purpose": "recap overview"}
        ],
        "how_to": [
            {"shot": "wide", "lens": "24mm", "purpose": "setup"},
            {"shot": "medium", "lens": "50mm", "purpose": "intro"},
            {"shot": "close", "lens": "85mm", "purpose": "step detail"},
            {"shot": "close", "lens": "85mm", "purpose": "step detail"},
            {"shot": "medium", "lens": "50mm", "purpose": "result"},
            {"shot": "wide", "lens": "35mm", "purpose": "outro"}
        ],
        "news_flash": [
            {"shot": "medium", "lens": "50mm", "purpose": "urgent open"},
            {"shot": "close", "lens": "85mm", "purpose": "key fact"},
            {"shot": "wide", "lens": "35mm", "purpose": "context"},
            {"shot": "medium", "lens": "50mm", "purpose": "impact"}
        ]
    }

    # Default to tutorial if format not found
    return SHOT_PROGRESSIONS.get(series_format_name, SHOT_PROGRESSIONS["tutorial"])


def _select_shot_type(scene_index: int, series_format_name: str) -> Dict:
    """
    Selects shot type for a specific scene based on progression.

    Args:
        scene_index: Scene position (0-based)
        series_format_name: Format name

    Returns:
        Shot spec dict with shot, lens, purpose
    """
    progression = _get_shot_progression(series_format_name)
    # Cycle through progression if we have more scenes
    return progression[scene_index % len(progression)]


def _select_camera_movement(segment_name: str) -> str:
    """
    Selects appropriate camera movement for segment type.

    Sora 2 Best Practice: One movement per scene, simple and choreographed.

    Args:
        segment_name: Segment type (hook, intro, content_X, outro)

    Returns:
        Camera movement description
    """
    CAMERA_MOVEMENTS = {
        "hook": "slow push in",  # engagement
        "intro": "static hold",  # stability
        "content": "slow dolly forward",  # reveal
        "outro": "slow zoom out"  # closure
    }

    # Match segment type
    if segment_name == "hook":
        return CAMERA_MOVEMENTS["hook"]
    elif segment_name == "intro":
        return CAMERA_MOVEMENTS["intro"]
    elif segment_name == "outro":
        return CAMERA_MOVEMENTS["outro"]
    else:
        return CAMERA_MOVEMENTS["content"]


def _get_lighting_design(vertical_id: str) -> Dict:
    """
    Returns lighting design specifications for a vertical.

    Args:
        vertical_id: Content vertical (finance, tech_ai, fitness, etc.)

    Returns:
        Lighting spec dict with mood, primary, direction, intensity, accents
    """
    LIGHTING_STYLES = {
        "finance": {
            "mood": "professional, trustworthy",
            "primary": "soft diffused daylight",
            "direction": "top-left key light",
            "intensity": "medium-high",
            "accents": "blue-tinted highlights for data viz"
        },
        "tech_ai": {
            "mood": "futuristic, energetic",
            "primary": "cool LED panels",
            "direction": "rim lighting from behind",
            "intensity": "high contrast",
            "accents": "cyan and magenta edge lights"
        },
        "fitness": {
            "mood": "motivational, dynamic",
            "primary": "natural golden hour",
            "direction": "side key with strong shadows",
            "intensity": "high",
            "accents": "warm orange accents"
        },
        "gaming": {
            "mood": "energetic, vibrant",
            "primary": "RGB LED gaming lights",
            "direction": "backlit with color cycling",
            "intensity": "high contrast",
            "accents": "neon purple and green"
        },
        "education": {
            "mood": "clear, focused",
            "primary": "soft overhead lighting",
            "direction": "even front key",
            "intensity": "medium",
            "accents": "warm white highlights"
        }
    }

    # Default to education for unknown verticals
    return LIGHTING_STYLES.get(vertical_id, LIGHTING_STYLES["education"])


def _generate_audio_cues(segment_name: str, ai_format: str, vertical_id: str) -> str:
    """
    Generates audio cue descriptions for Sora 2 prompts.

    Sora 2 Best Practice: Specify ambient sounds and effects for richer output.

    Args:
        segment_name: Segment type
        ai_format: Visual format (animated_infographics, kinetic_typography, etc.)
        vertical_id: Content vertical

    Returns:
        Audio cue description string
    """
    # Format-specific audio patterns
    FORMAT_AUDIO = {
        "animated_infographics": {
            "hook": "attention-grabbing notification chime",
            "content": "data point ping sounds, subtle chart whooshes",
            "outro": "completion tone"
        },
        "kinetic_typography": {
            "hook": "bold text impact sound",
            "content": "text slide whooshes, rhythmic beats",
            "outro": "fade to silence"
        },
        "cinematic_broll": {
            "hook": "dramatic ambient swell",
            "content": "environmental sounds matching scene",
            "outro": "soft fade out"
        },
        "whiteboard_animation": {
            "hook": "pen writing sound",
            "content": "drawing sounds, subtle paper texture",
            "outro": "final stroke completion"
        },
        "code_visualization": {
            "hook": "terminal startup beep",
            "content": "keyboard typing, code execution sounds",
            "outro": "process complete chime"
        }
    }

    # Vertical ambient sounds
    VERTICAL_AMBIENT = {
        "finance": "subtle keyboard typing, professional office atmosphere",
        "tech_ai": "soft tech ambience, data processing hum",
        "fitness": "motivational background energy",
        "gaming": "ambient game UI sounds"
    }

    # Get format-specific audio
    format_audio_dict = FORMAT_AUDIO.get(ai_format, FORMAT_AUDIO["cinematic_broll"])
    segment_type = "hook" if segment_name == "hook" else ("outro" if segment_name == "outro" else "content")
    format_audio = format_audio_dict[segment_type]

    # Add vertical ambient if available
    vertical_ambient = VERTICAL_AMBIENT.get(vertical_id, "")

    if vertical_ambient:
        return f"{format_audio}, {vertical_ambient}"
    return format_audio


def _get_emotional_context(segment_name: str, scene_index: int, total_scenes: int) -> Dict:
    """
    Returns emotional energy level and story beat role for retention optimization.

    Sora 2 Best Practice: Orchestrate emotional pacing to prevent retention drops.
    Research shows viewers drop off at seconds 4-7 if energy plateaus.

    Energy Levels:
    - HIGH: Maximum impact, attention grab (hook scenes)
    - BUILDING: Rising tension, curiosity build (problem/challenge scenes)
    - PEAK: Maximum engagement, climax moment (key insight/solution)
    - RELEASE: Satisfaction, resolution (solution delivery)
    - CALL_ACTION: Invitation energy, direct address (CTA scenes)

    Story Beats (Italian naming for script consistency):
    - GRABBER: Stop-scroll hook, immediate attention
    - TENSIONE: Problem/challenge presentation, build curiosity
    - RIVELAZIONE: Key insight or surprising data point
    - SOLUZIONE: Solution/answer delivery, value provision
    - CTA: Call-to-action, direct invitation

    Args:
        segment_name: Segment type (hook, problem, solution, cta, content_X, etc.)
        scene_index: Scene position (0-based)
        total_scenes: Total number of content scenes

    Returns:
        Dict with energy_level (str), story_beat (str), pacing_note (str)

    Example:
        >>> ctx = _get_emotional_context("hook", 0, 4)
        >>> ctx["energy_level"]
        'HIGH'
        >>> ctx["story_beat"]
        'GRABBER'
    """
    # Energy progression mapping by segment type
    SEGMENT_EMOTIONAL_MAP = {
        "hook": {
            "energy_level": "HIGH",
            "story_beat": "GRABBER",
            "pacing_note": "Maximum impact - stop scroll within 2 seconds"
        },
        "problem": {
            "energy_level": "BUILDING",
            "story_beat": "TENSIONE",
            "pacing_note": "Rising curiosity - create empathy and investment"
        },
        "solution": {
            "energy_level": "RELEASE",
            "story_beat": "SOLUZIONE",
            "pacing_note": "Satisfying payoff - deliver value and resolution"
        },
        "cta": {
            "energy_level": "CALL_ACTION",
            "story_beat": "CTA",
            "pacing_note": "Inviting energy - direct friendly address"
        },
        "intro": {
            "energy_level": "HIGH",
            "story_beat": "GRABBER",
            "pacing_note": "Establish presence - confident opening"
        },
        "outro": {
            "energy_level": "CALL_ACTION",
            "story_beat": "CTA",
            "pacing_note": "Memorable close - invitation to engage"
        }
    }

    # Handle generic content_X segments with position-based logic
    if segment_name.startswith("content_"):
        # Distribute energy across content scenes to prevent plateau
        scene_position_ratio = scene_index / max(total_scenes - 1, 1)

        if scene_position_ratio < 0.33:
            # Early content: Build tension
            return {
                "energy_level": "BUILDING",
                "story_beat": "TENSIONE",
                "pacing_note": "Build curiosity - introduce complexity"
            }
        elif scene_position_ratio < 0.66:
            # Mid content: Peak moment
            return {
                "energy_level": "PEAK",
                "story_beat": "RIVELAZIONE",
                "pacing_note": "Key insight - deliver surprising value"
            }
        else:
            # Late content: Release to solution
            return {
                "energy_level": "RELEASE",
                "story_beat": "SOLUZIONE",
                "pacing_note": "Payoff delivery - satisfy curiosity"
            }

    # Look up segment in map, default to BUILDING if not found
    emotional_context = SEGMENT_EMOTIONAL_MAP.get(
        segment_name,
        {
            "energy_level": "BUILDING",
            "story_beat": "TENSIONE",
            "pacing_note": "Maintain engagement - progressive reveal"
        }
    )

    return emotional_context


def _build_7layer_cinematic_prompt(
    scene_context: Dict,
    cinematic_specs: Dict,
    audio_design: str,
    brand_identity: Dict,
    ai_format: str,
    segment_text: str,
    emotional_context: Optional[Dict] = None
) -> str:
    """
    Builds a 7-layer cinematic prompt structure following Sora 2 best practices.

    Layers:
    1. Scena e ambientazione
    2. Soggetto e azione
    3. Inquadratura e camera
    4. Illuminazione e colori
    5. Dettagli fisici e materiali
    6. Audio e suoni
    7. Esclusioni (negazioni)
    8. BONUS: Energy level (retention optimization)

    Args:
        scene_context: Dict with topic, duration, segment_name
        cinematic_specs: Dict with shot, lens, purpose, camera_movement, lighting
        audio_design: Audio cues string
        brand_identity: Dict with colors (primary, secondary, accent), format
        ai_format: Visual format (animated_infographics, etc.)
        segment_text: Scene voiceover text for content description
        emotional_context: Optional dict with energy_level, story_beat, pacing_note

    Returns:
        Cinematic prompt string optimized for Sora 2/Veo
    """
    shot = cinematic_specs['shot']
    lens = cinematic_specs['lens']
    purpose = cinematic_specs['purpose']
    camera_movement = cinematic_specs['camera_movement']
    lighting = cinematic_specs['lighting']

    colors = brand_identity['colors']
    topic = scene_context['topic']

    # Extract content preview from segment_text (first 50 chars or key phrase)
    content_preview = segment_text[:50] + "..." if len(segment_text) > 50 else segment_text

    # Build prompt following 7-layer structure
    prompt_parts = []

    # LAYER 1: SCENA E AMBIENTAZIONE
    prompt_parts.append(f"{shot.capitalize()} shot")

    # LAYER 2: SOGGETTO E AZIONE (format-specific + content-specific)
    if ai_format == "animated_infographics":
        prompt_parts.append(f"showing: {content_preview}. Animated data visualization")
    elif ai_format == "kinetic_typography":
        prompt_parts.append(f"with text: {content_preview}. Bold kinetic typography animation")
    elif ai_format == "cinematic_broll":
        prompt_parts.append(f"illustrating: {content_preview}. Professional b-roll footage")
    elif ai_format == "code_visualization":
        prompt_parts.append(f"demonstrating: {content_preview}. Code editor visualization")
    elif ai_format == "whiteboard_animation":
        prompt_parts.append(f"explaining: {content_preview}. Hand-drawn whiteboard animation")
    else:
        prompt_parts.append(f"about: {content_preview}")

    # LAYER 3: INQUADRATURA E CAMERA
    prompt_parts.append(f"{lens} lens, {camera_movement}, {purpose}")

    # LAYER 4: ILLUMINAZIONE E COLORI
    prompt_parts.append(
        f"{lighting['primary']}, {lighting['direction']}, "
        f"{colors['primary']} primary, {colors['secondary']} secondary, "
        f"{colors['accent']} accents, {lighting['mood']} mood"
    )

    # LAYER 5: DETTAGLI FISICI
    prompt_parts.append("smooth professional surfaces, crisp high-definition quality")

    # LAYER 6: AUDIO E SUONI
    prompt_parts.append(f"Audio: {audio_design}")

    # LAYER 7: ESCLUSIONI
    if "faceless" in brand_identity.get('mode', ''):
        prompt_parts.append("NO PEOPLE VISIBLE")

    # LAYER 8 (BONUS): ENERGY LEVEL (retention optimization)
    if emotional_context:
        energy_level = emotional_context['energy_level']
        story_beat = emotional_context['story_beat']

        # Map energy levels to visual descriptors
        energy_descriptors = {
            "HIGH": "maximum visual energy, bold dynamic movement",
            "BUILDING": "rising tension, progressive reveal",
            "PEAK": "climactic moment, striking visual impact",
            "RELEASE": "satisfying resolution, smooth delivery",
            "CALL_ACTION": "inviting energy, direct engagement"
        }

        energy_desc = energy_descriptors.get(energy_level, "engaging pacing")
        prompt_parts.append(f"Energy: {energy_desc} ({story_beat} beat)")

    # Add vertical format constraint
    prompt_parts.append("Vertical 9:16 format optimized for mobile")

    # Combine all layers
    prompt = ". ".join(prompt_parts) + "."

    return prompt


def _generate_cinematic_scene_prompt(
    segment_name: str,
    segment_text: str,
    plan: VideoPlan,
    scene_index: int,
    total_scenes: int,
    series_format_name: str,
    vertical_id: str,
    ai_format: str,
    brand_manual: Dict,
    is_faceless: bool = True
) -> str:
    """
    Generates a cinematic scene prompt integrating all Sora 2 best practices.

    This is the master function that orchestrates:
    - Shot type progression (wide/medium/close variety)
    - Camera movement choreography
    - Lighting design per vertical
    - Audio cues generation
    - 7-layer prompt structure
    - Content-specific descriptions

    Args:
        segment_name: Segment type (hook, intro, content_X, outro)
        segment_text: Scene voiceover text
        plan: Video plan for context
        scene_index: Scene position (0-based)
        total_scenes: Total number of scenes
        series_format_name: Format name (tutorial, how_to, news_flash)
        vertical_id: Content vertical (finance, tech_ai, etc.)
        ai_format: Visual format (animated_infographics, etc.)
        brand_manual: Brand identity with color palette
        is_faceless: Whether video is faceless (no people)

    Returns:
        Cinematic Veo/Sora prompt string
    """
    # Step 1: Select shot type based on progression
    shot_specs = _select_shot_type(scene_index, series_format_name)

    # Step 2: Select camera movement
    camera_movement = _select_camera_movement(segment_name)

    # Step 3: Get lighting design for vertical
    lighting = _get_lighting_design(vertical_id)

    # Step 4: Generate audio cues
    audio_cues = _generate_audio_cues(segment_name, ai_format, vertical_id)

    # Step 5: Extract brand colors
    palette = brand_manual.get('color_palette', {}) if brand_manual else {}
    colors = {
        'primary': palette.get('primary', '#1976D2'),
        'secondary': palette.get('secondary', '#4CAF50'),
        'accent': palette.get('accent', '#FFC107'),
        'background': palette.get('background', '#263238')
    }

    # Step 6: Build cinematic specs bundle
    cinematic_specs = {
        'shot': shot_specs['shot'],
        'lens': shot_specs['lens'],
        'purpose': shot_specs['purpose'],
        'camera_movement': camera_movement,
        'lighting': lighting
    }

    scene_context = {
        'topic': plan.working_title,
        'duration': 0,  # Will be calculated later
        'segment_name': segment_name
    }

    brand_identity = {
        'colors': colors,
        'format': ai_format,
        'mode': 'faceless' if is_faceless else 'character'
    }

    # Step 7: Build 7-layer cinematic prompt
    prompt = _build_7layer_cinematic_prompt(
        scene_context=scene_context,
        cinematic_specs=cinematic_specs,
        audio_design=audio_cues,
        brand_identity=brand_identity,
        ai_format=ai_format,
        segment_text=segment_text
    )

    logger.debug(
        f"  Generated cinematic prompt for scene {scene_index + 1}: "
        f"{shot_specs['shot']} shot, {camera_movement}, {ai_format}"
    )

    return prompt


def _optimize_hook_scene(
    hook_text: str,
    plan: VideoPlan,
    ai_format: str,
    brand_colors: Dict,
    vertical_id: str
) -> str:
    """
    Optimizes the first scene as a visual HOOK for maximum impact.

    Sora 2 Best Practice: First 2-3 seconds are crucial for retention.
    Create stunning, attention-grabbing opening that stops scrolling.

    Args:
        hook_text: Hook voiceover text
        plan: Video plan
        ai_format: Visual format
        brand_colors: Color palette
        vertical_id: Content vertical

    Returns:
        Hook-optimized cinematic prompt
    """
    # Hook strategies per format
    HOOK_STRATEGIES = {
        "animated_infographics": "Bold data reveal with dramatic chart rise",
        "kinetic_typography": "Text burst onto screen with high impact",
        "cinematic_broll": "Stunning visual establishing shot",
        "code_visualization": "Terminal boot sequence with dramatic reveal",
        "whiteboard_animation": "Hand draws attention-grabbing element"
    }

    hook_strategy = HOOK_STRATEGIES.get(ai_format, "Dynamic opening with visual energy")

    # Get lighting for dramatic effect
    lighting = _get_lighting_design(vertical_id)

    # Build hook-optimized prompt
    prompt = (
        f"HOOK SCENE - Maximum Impact Opening. "
        f"MEDIUM SHOT with SLOW PUSH IN for engagement. "
        f"{hook_strategy}. "
        f"Content: \"{hook_text[:40]}...\". "
        f"High visual energy with {brand_colors['accent']} accent pops. "
        f"{lighting['primary']}, {lighting['accents']}. "
        f"Immediate visual interest - show most compelling element FIRST. "
        f"Purpose: Stop scroll, capture attention within first 2 seconds. "
        f"Vertical 9:16 format."
    )

    logger.info(f"  🎯 Hook scene optimized for maximum impact retention")

    return prompt


def _generate_ai_enhanced_scene_prompt(
    segment_name: str,
    segment_text: str,
    plan: VideoPlan,
    scene_index: int,
    total_scenes: int,
    series_format_name: str,
    vertical_id: str,
    ai_format: str,
    brand_manual: Dict,
    brand_tone: str,
    narrator_persona: Optional[Dict],
    target_language: str,
    recent_titles: List[str],
    previous_scene_composition: Optional[Dict] = None,
    character_description: Optional[str] = None,
    video_style_mode: str = "faceless"
) -> Dict:
    """
    AI-enhanced scene prompt using LLM with FULL workspace context.

    This is the TRUE AI-driven implementation that:
    - Calls LLM for each scene with rich context
    - Incorporates ALL workspace configs (brand_tone, narrator, language, history)
    - Generates creative, personalized prompts
    - Falls back to deterministic if LLM fails
    - Maintains spatial continuity with previous scene composition
    - Supports BOTH faceless and character-based modes

    Args:
        segment_name: Segment type (hook, content_X, outro)
        segment_text: Scene voiceover text
        plan: Video plan
        scene_index: Scene position (0-based)
        total_scenes: Total scenes count
        series_format_name: Format name (tutorial, how_to, news_flash)
        vertical_id: Content vertical (finance, tech_ai, etc.)
        ai_format: Visual format (animated_infographics, etc.) or "character_based"
        brand_manual: Brand identity with color palette
        brand_tone: Brand personality from workspace
        narrator_persona: Narrator identity (optional)
        target_language: Content language (en, it, etc.)
        recent_titles: Past successful video titles
        previous_scene_composition: Optional dict with shot, setting, spatial_anchor from previous scene
        character_description: Optional character identity anchor for character-based mode
        video_style_mode: "faceless" or "character_based"

    Returns:
        Dict with 'prompt' (str) and 'composition' (dict for next scene)
    """
    # Step 1: Gather all cinematic specs (for context and fallback)
    shot_specs = _select_shot_type(scene_index, series_format_name)
    camera_movement = _select_camera_movement(segment_name)
    lighting = _get_lighting_design(vertical_id)
    audio_cues = _generate_audio_cues(segment_name, ai_format, vertical_id)

    # Step 1b: Get emotional context for retention optimization
    emotional_context = _get_emotional_context(segment_name, scene_index, total_scenes)

    # Step 2: Extract brand colors
    palette = brand_manual.get('color_palette', {}) if brand_manual else {}
    colors = {
        'primary': palette.get('primary', '#1976D2'),
        'secondary': palette.get('secondary', '#4CAF50'),
        'accent': palette.get('accent', '#FFC107'),
        'background': palette.get('background', '#263238')
    }

    # Step 3: Build rich LLM context
    narrator_context = ""
    if narrator_persona and narrator_persona.get('enabled'):
        narrator_context = f"""
NARRATOR PERSONA:
- Name: {narrator_persona.get('name', 'N/A')}
- Identity: {narrator_persona.get('identity', 'N/A')}
- Relationship: {narrator_persona.get('relationship', 'N/A')}
"""

    # Step 3b: Build character context for character-based mode
    character_context = ""
    if character_description and video_style_mode == "character_based":
        character_context = f"""
CHARACTER IDENTITY (Character-Based Mode):
- {character_description}
- CRITICAL: This character MUST be visible and consistent across ALL scenes
- Maintain same person, clothing, and appearance throughout the video
"""

    recent_context = ""
    if recent_titles:
        recent_context = f"Recent successful videos: {', '.join(recent_titles[:3])}"

    # Step 4: Build spatial continuity context
    spatial_continuity_context = ""
    if previous_scene_composition and scene_index > 0:
        # We have composition from previous scene - maintain spatial anchors
        prev_setting = previous_scene_composition.get('setting', 'same environment')
        prev_anchor = previous_scene_composition.get('spatial_anchor', 'consistent framing')
        prev_shot = previous_scene_composition.get('shot', 'similar composition')

        spatial_continuity_context = f"""⚠️ CRITICAL FOR SORA CONSISTENCY:
- Previous scene setting: {prev_setting}
- Maintain spatial anchor: {prev_anchor}
- Camera remains in: {prev_shot} perspective
- DO NOT change the "virtual set" - keep same background/environment
- Only change shot distance ({shot_specs['shot']}) while keeping same spatial location
- This creates seamless flow and prevents Sora from "jumping" to different locations"""
    else:
        # First scene - establish the spatial anchor
        spatial_continuity_context = f"""This is the FIRST scene - establish the spatial anchor:
- Define a clear setting/environment for the {ai_format} format
- Create a "virtual set" that can persist across all scenes
- Establish clear spatial references that can be maintained
- Example: Same desk/workspace, same data viz canvas, same virtual space"""

    llm_prompt = f"""You are a professional cinematographer generating Sora 2/Veo video prompts.

VIDEO IDENTITY:
- Title: {plan.working_title}
- Strategic Angle: {plan.strategic_angle}
- Vertical: {vertical_id}
- Series Format: {series_format_name}
- Brand Tone: {brand_tone}
- Target Language: {target_language}

BRAND VISUAL IDENTITY:
- Visual Format: {ai_format} (STRICT - must use ONLY this format throughout)
- Primary Color: {colors['primary']}
- Secondary Color: {colors['secondary']}
- Accent Color: {colors['accent']}
- Background: {colors['background']}
{narrator_context}{character_context}
EMOTIONAL ORCHESTRATION (Retention Optimization):
- Energy Level: {emotional_context['energy_level']} (governs visual intensity)
- Story Beat: {emotional_context['story_beat']} (narrative role in arc)
- Pacing Goal: {emotional_context['pacing_note']}
⚠️ CRITICAL: Match visual energy to this level to prevent retention drop at seconds 4-7.

SCENE CONTEXT:
- Position: Scene {scene_index + 1} of {total_scenes}
- Segment Type: {segment_name}
- Voiceover Content: "{segment_text}"
- Purpose: {shot_specs['purpose']}

CINEMATIC REQUIREMENTS (7-Layer Structure):

1. SCENA E AMBIENTAZIONE:
   - Appropriate setting for: {plan.working_title}
   - Lighting mood: {lighting['mood']}

2. SOGGETTO E AZIONE:
   - Visual content MUST show: "{segment_text[:60]}..."
   - Format style: {ai_format} (NO mixing formats!)

3. INQUADRATURA E CAMERA:
   - Shot type: {shot_specs['shot']} shot ({shot_specs['lens']} lens)
   - Camera movement: {camera_movement}
   - Composition purpose: {shot_specs['purpose']}

4. ILLUMINAZIONE E COLORI:
   - Primary lighting: {lighting['primary']}
   - Direction: {lighting['direction']}
   - Intensity: {lighting['intensity']}
   - Brand colors: Primary {colors['primary']}, Secondary {colors['secondary']}, Accent {colors['accent']}

5. DETTAGLI FISICI:
   - Smooth professional surfaces
   - Crisp high-definition quality
   - Realistic physics

6. AUDIO E SUONI:
   - {audio_cues}

7. ESCLUSIONI:
   - {"NO PEOPLE VISIBLE (faceless format)" if video_style_mode == "faceless" else "Character MUST be visible and consistent (character-based format)"}
   - NO text logos or branding
   - NO unrealistic physics

SPATIAL CONTINUITY (Frame-to-Frame Composition Persistence):
{spatial_continuity_context}

CONSISTENCY REQUIREMENTS:
- This is scene {scene_index + 1} of a {total_scenes}-scene continuous video
- Maintain visual continuity with other scenes
- Same {ai_format} format and lighting style throughout
- Vertical 9:16 aspect ratio optimized for mobile
- CRITICAL: Keep the same "virtual set" across scenes for seamless flow

{recent_context}

TASK:
Generate a 300-500 character Sora 2/Veo prompt that synthesizes all 7 layers into ONE cohesive, cinematic description.
Be specific, concrete, and visual. The prompt should be ready to use directly with Sora/Veo API.
Focus on describing what will be SEEN and HEARD in this specific scene.

OUTPUT FORMAT: Direct prompt text only, no explanations."""

    # Step 4: Call LLM with error handling
    try:
        from yt_autopilot.services.llm_router import generate_text

        logger.debug(f"  🤖 Calling LLM for AI-enhanced scene {scene_index + 1} prompt...")

        response = generate_text(
            role="cinematographer",
            task=llm_prompt,
            context="",  # Context is in task
            style_hints={"temperature": 0.7}  # Creative but not too random
        )

        prompt = response.strip()

        logger.info(f"  ✓ AI-enhanced prompt generated for scene {scene_index + 1} ({len(prompt)} chars)")

        # Build composition info for next scene's spatial continuity
        current_composition = {
            'shot': shot_specs['shot'],
            'setting': f"{ai_format} virtual environment",
            'spatial_anchor': f"{lighting['mood']} lit {ai_format} space with {colors['primary']} tones"
        }

        return {
            'prompt': prompt,
            'composition': current_composition
        }

    except Exception as e:
        logger.warning(f"  ⚠️ AI prompt generation failed for scene {scene_index + 1}: {e}")
        logger.info(f"  → Falling back to deterministic prompt generation")

        # Step 5: Fallback to deterministic system
        scene_context = {
            'topic': plan.working_title,
            'duration': 0,
            'segment_name': segment_name
        }

        cinematic_specs = {
            'shot': shot_specs['shot'],
            'lens': shot_specs['lens'],
            'purpose': shot_specs['purpose'],
            'camera_movement': camera_movement,
            'lighting': lighting
        }

        brand_identity = {
            'colors': colors,
            'format': ai_format,
            'mode': video_style_mode
        }

        fallback_prompt = _build_7layer_cinematic_prompt(
            scene_context=scene_context,
            cinematic_specs=cinematic_specs,
            audio_design=audio_cues,
            brand_identity=brand_identity,
            ai_format=ai_format,
            segment_text=segment_text,
            emotional_context=emotional_context  # Pass emotional context to fallback
        )

        # Build composition info for next scene (same as success path)
        current_composition = {
            'shot': shot_specs['shot'],
            'setting': f"{ai_format} virtual environment",
            'spatial_anchor': f"{lighting['mood']} lit {ai_format} space with {colors['primary']} tones"
        }

        return {
            'prompt': fallback_prompt,
            'composition': current_composition
        }


def _select_faceless_theme(faceless_config: Dict, segment_name: str) -> Optional[Dict]:
    """
    Selects a visual theme for faceless b-roll based on segment type.

    Step 09.6: Faceless Video Mode - theme-based prompt generation without people.

    Args:
        faceless_config: Faceless configuration from workspace with visual_themes
        segment_name: Segment type (hook, content_X, outro)

    Returns:
        Selected theme dict with theme_id, name, description, or None if no themes

    Example:
        >>> config = {"visual_themes": [{"theme_id": "charts", "use_frequency": 0.6}]}
        >>> theme = _select_faceless_theme(config, "hook")
        >>> theme["theme_id"]
        'charts'
    """
    if not faceless_config:
        return None

    themes = faceless_config.get('visual_themes', [])
    if not themes:
        return None

    # Weighted random selection based on use_frequency
    weights = [theme.get('use_frequency', 0.25) for theme in themes]
    selected_theme = random.choices(themes, weights=weights, k=1)[0]

    logger.debug(f"  Faceless theme selected: {selected_theme.get('name')} (segment: {segment_name})")

    return selected_theme


def _generate_faceless_prompt(
    segment_name: str,
    segment_text: str,
    plan: VideoPlan,
    visual_style: str,
    ai_format: str,
    brand_manual: Optional[Dict] = None
) -> str:
    """
    Generates format-specific faceless prompt for Veo/Sora (NO PEOPLE visible).

    Step 09.7: AI-driven format selection - applies consistent visual format across all scenes.

    Args:
        segment_name: Name of the segment (hook, content_1, etc.)
        segment_text: Text content of the segment
        plan: Video plan for context
        visual_style: Channel's visual style from memory
        ai_format: AI-selected format ID (e.g., 'kinetic_typography', 'animated_infographics')
        brand_manual: Optional visual brand manual with color palette

    Returns:
        Format-specific Veo/Sora prompt string

    Example Prompts by Format:
        kinetic_typography: "Animated text motion graphics: 'MARKET CRASHES 30%' appears
                            with kinetic energy, bold sans-serif typography..."
        animated_infographics: "Data visualization animation: stock market chart rising
                               with animated candlesticks, numbers counting up..."
    """
    # Extract key visual elements
    is_vertical = "verticali" in visual_style.lower() or "9:16" in visual_style.lower()

    # Extract color palette from brand manual if enabled
    color_description = None
    if brand_manual and brand_manual.get('enabled'):
        palette = brand_manual.get('color_palette', {})
        if palette:
            primary = palette.get('primary', '')
            secondary = palette.get('secondary', '')
            accent = palette.get('accent', '')
            background = palette.get('background', '')
            color_description = (
                f"{primary} primary, {secondary} secondary, {accent} accents, {background} background"
            )

    # Use color from brand manual or default
    colors = color_description if color_description else "professional vibrant colors"

    # Content topic for context
    topic = plan.working_title

    # Format-specific prompt generation
    if ai_format == "whiteboard_animation":
        if segment_name == "hook":
            prompt = (
                f"Whiteboard animation style: Hand-drawn sketch appearing on white background. "
                f"Topic: {topic}. NO PEOPLE VISIBLE, only the drawing hand and whiteboard. "
                f"Bold marker strokes revealing key concept, {colors}, fast energetic drawing, "
                f"educational aesthetic, clean minimalist style. Vertical 9:16 format."
            )
        else:
            prompt = (
                f"Whiteboard animation: Hand drawing explains {topic}. "
                f"NO PEOPLE VISIBLE, only drawing hand. Diagrams, arrows, text appearing progressively, "
                f"{colors}, clear educational style, marker on whiteboard, step-by-step visual explanation. "
                f"Vertical 9:16 format."
            )

    elif ai_format == "kinetic_typography":
        if segment_name == "hook":
            prompt = (
                f"Kinetic typography animation: Bold text '{segment_text[:40]}...' bursts onto screen. "
                f"NO PEOPLE VISIBLE. Dynamic text movement, {colors}, modern sans-serif fonts, "
                f"motion graphics energy, text scales/rotates/zooms, high impact opening. "
                f"Vertical 9:16 format optimized for mobile."
            )
        else:
            prompt = (
                f"Kinetic typography: Animated text explaining {topic}. NO PEOPLE VISIBLE. "
                f"Words appear with motion graphics energy, {colors}, smooth transitions, "
                f"bold modern fonts, text emphasis through scale and movement. "
                f"Vertical 9:16 format."
            )

    elif ai_format == "animated_infographics":
        if segment_name == "hook":
            prompt = (
                f"Animated infographic: Data visualization about {topic} appears dynamically. "
                f"NO PEOPLE VISIBLE. Charts rising, numbers counting up, {colors}, "
                f"clean modern design, icons and graphs animating in, professional data viz aesthetic. "
                f"Vertical 9:16 format."
            )
        else:
            prompt = (
                f"Animated infographic: {topic} explained through data visualization. "
                f"NO PEOPLE VISIBLE. Bar charts, pie charts, line graphs animating smoothly, "
                f"{colors}, clean professional design, numbers and percentages appearing, "
                f"educational data-driven aesthetic. Vertical 9:16 format."
            )

    elif ai_format == "podcast_style":
        if segment_name == "hook":
            prompt = (
                f"Podcast visual style: Audio waveform pulsing with voice about {topic}. "
                f"NO PEOPLE VISIBLE. Animated waveform visualization, {colors}, "
                f"minimal aesthetic, frequency bars moving to speech rhythm, clean modern design. "
                f"Vertical 9:16 format."
            )
        else:
            prompt = (
                f"Podcast visual: Audio waveform visualization for {topic} discussion. "
                f"NO PEOPLE VISIBLE. Smooth waveform animation, {colors}, minimal clean design, "
                f"frequency visualization, text captions appearing, audio-focused aesthetic. "
                f"Vertical 9:16 format."
            )

    elif ai_format == "stop_motion":
        if segment_name == "hook":
            prompt = (
                f"Stop-motion animation: Objects related to {topic} move frame-by-frame. "
                f"NO PEOPLE VISIBLE (only hands may appear briefly moving objects). "
                f"{colors}, creative handmade aesthetic, physical objects, charming stop-motion style, "
                f"unique visual appeal. Vertical 9:16 format."
            )
        else:
            prompt = (
                f"Stop-motion animation: {topic} explained through physical objects. "
                f"NO PEOPLE VISIBLE (only hands may briefly move objects). "
                f"Frame-by-frame movement, {colors}, creative handcrafted style, "
                f"physical props and materials, charming stop-motion aesthetic. "
                f"Vertical 9:16 format."
            )

    elif ai_format == "code_visualization":
        if segment_name == "hook":
            prompt = (
                f"Code visualization: Terminal screen showing code related to {topic}. "
                f"NO PEOPLE VISIBLE. Code appearing line-by-line, {colors}, "
                f"syntax highlighting, cursor blinking, developer aesthetic, "
                f"clean monospace font, dark terminal theme. Vertical 9:16 format."
            )
        else:
            prompt = (
                f"Code visualization: Programming code demonstrating {topic}. "
                f"NO PEOPLE VISIBLE. Code editor with syntax highlighting, {colors}, "
                f"code scrolling/typing animation, terminal commands executing, "
                f"technical developer aesthetic, clean code display. Vertical 9:16 format."
            )

    else:  # cinematic_broll (default fallback)
        if segment_name == "hook":
            prompt = (
                f"Cinematic b-roll: High-quality stock footage about {topic}. "
                f"NO PEOPLE VISIBLE, NO FACES. Professional objects and concepts, {colors}, "
                f"dramatic lighting, slow cinematic camera movement, high production value, "
                f"engaging visual storytelling. Vertical 9:16 format."
            )
        elif segment_name == "outro":
            prompt = (
                f"Inspirational b-roll: Aspirational visuals about {topic}. "
                f"NO PEOPLE VISIBLE, NO FACES. Success symbols and concepts, {colors}, "
                f"uplifting atmosphere, smooth camera movement, motivational aesthetic, "
                f"positive emotional tone. Vertical 9:16 format."
            )
        else:
            prompt = (
                f"Professional b-roll: Stock footage explaining {topic}. "
                f"NO PEOPLE VISIBLE, NO FACES. Clear visual concepts, {colors}, "
                f"informative aesthetic, smooth camera work, educational clarity, "
                f"professional production quality. Vertical 9:16 format."
            )

    return prompt


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
    visual_style: str,
    brand_manual: Optional[Dict] = None,
    visual_context: Optional[Dict] = None,
    character_description: Optional[str] = None
) -> str:
    """
    Generates a descriptive prompt for Veo video generation API.

    Step 09: Enhanced with color palette enforcement from brand manual
             and visual context support for recurring scenarios.
    Step 09.5: Enhanced with character consistency support.

    Args:
        segment_name: Name of the segment (hook, content_1, etc.)
        segment_text: Text content of the segment
        plan: Video plan for context
        visual_style: Channel's visual style from memory
        brand_manual: Optional visual brand manual with color palette (Step 09)
        visual_context: Optional visual context with veo_prompt_prefix (Step 09)
        character_description: Optional character identity anchor for consistency (Step 09.5)

    Returns:
        Veo-compatible prompt string
    """
    # Base style elements from memory
    # Expected: "Ritmo alto, colori caldi, testo grande in sovrimpressione stile Shorts verticali"

    # Extract key visual elements
    has_warm_colors = "caldi" in visual_style.lower()
    has_text_overlay = "testo" in visual_style.lower()
    is_vertical = "verticali" in visual_style.lower() or "9:16" in visual_style.lower()

    # Step 09: Extract color palette from brand manual if enabled
    color_description = None
    if brand_manual and brand_manual.get('enabled'):
        palette = brand_manual.get('color_palette', {})
        if palette:
            # Build color description from palette
            primary = palette.get('primary', '')
            secondary = palette.get('secondary', '')
            accent = palette.get('accent', '')
            background = palette.get('background', '')

            color_description = (
                f"vibrant {primary} primary tones with {secondary} accents, "
                f"{accent} highlights, cinematic {background} backgrounds"
            )

    # Step 09: Use color_description from brand manual if available, else fall back to legacy logic
    if color_description:
        # Brand manual enabled - use specific color palette
        colors_hook = color_description
        colors_content = color_description
        colors_outro = color_description
    else:
        # Legacy color logic
        colors_hook = 'warm vibrant colors' if has_warm_colors else 'bold colors'
        colors_content = 'warm color palette' if has_warm_colors else 'professional colors'
        colors_outro = 'warm friendly colors' if has_warm_colors else 'bright colors'

    # Step 09: Extract visual context prefix if provided
    context_prefix = ""
    if visual_context:
        context_prefix = visual_context.get('veo_prompt_prefix', '')
        if context_prefix:
            context_prefix = context_prefix + ". "  # Add period and space as separator

    # Step 09.5: Add character description after context
    character_prefix = ""
    if character_description:
        character_prefix = character_description + ". "

    # Build prompt based on segment type
    if segment_name == "hook":
        # Hook: attention-grabbing, dynamic
        prompt = (
            f"{context_prefix}"  # Step 09: Prepend visual context
            f"{character_prefix}"  # Step 09.5: Character identity anchor
            f"Dynamic vertical video shot, {plan.working_title} theme. "
            f"Fast-paced camera movement, {colors_hook}, "
            f"modern aesthetic. High energy opening sequence. "
            f"{'Large text overlay visible' if has_text_overlay else 'Clean visual focus'}. "
            f"Cinematic lighting, professional quality."
        )

    elif segment_name.startswith("content"):
        # Content: informative, clear
        prompt = (
            f"{context_prefix}"  # Step 09: Prepend visual context
            f"{character_prefix}"  # Step 09.5: Character identity anchor
            f"Engaging vertical video, explaining {plan.working_title}. "
            f"Clean composition, {colors_content}, "
            f"informative visual elements. Smooth camera transitions. "
            f"{'Key text overlays for emphasis' if has_text_overlay else 'Visual clarity'}. "
            f"Modern production style."
        )

    elif segment_name == "outro":
        # Outro: call-to-action, memorable
        prompt = (
            f"{context_prefix}"  # Step 09: Prepend visual context
            f"{character_prefix}"  # Step 09.5: Character identity anchor
            f"Closing vertical video shot, {plan.working_title} conclusion. "
            f"Positive and inviting atmosphere, {colors_outro}, "
            f"call-to-action visual. "
            f"{'Large CTA text overlay' if has_text_overlay else 'Engaging final frame'}. "
            f"Professional quality finish."
        )

    else:
        # Generic fallback
        prompt = (
            f"{context_prefix}"  # Step 09: Prepend visual context
            f"{character_prefix}"  # Step 09.5: Character identity anchor
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
    series_format: Optional[SeriesFormat] = None,
    workspace_config: Optional[Dict] = None
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

    Step 09: Color palette enforcement from visual_brand_manual.
    If workspace_config contains visual_brand_manual with color palette,
    enforces those colors in Veo prompts.

    Optimized for YouTube Shorts (vertical 9:16 format, ~60 seconds total).

    Args:
        plan: Video plan with topic and context
        script: Complete video script (with scene_voiceover_map in Step 07.3+)
        memory: Channel memory dict containing visual_style
        series_format: Optional series format template for intro/outro (Step 07.5)
        workspace_config: Optional workspace configuration with visual_brand_manual (Step 09)

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

    # Step 09: Extract visual brand manual if provided
    brand_manual = None
    if workspace_config:
        brand_manual = workspace_config.get('visual_brand_manual', {})
        if brand_manual and brand_manual.get('enabled'):
            palette = brand_manual.get('color_palette', {})
            logger.info(f"  Using workspace color palette: primary={palette.get('primary')}, "
                       f"secondary={palette.get('secondary')}, accent={palette.get('accent')}")

    # Step 09: Select visual context for content scenes if enabled
    visual_context = None
    if workspace_config:
        visual_contexts_config = workspace_config.get('visual_contexts', {})
        visual_context = _select_visual_context(series_format, visual_contexts_config)

    # Step 09.5: Extract character profile and build description if enabled
    character_description = None
    character_profile_id = None
    if workspace_config:
        character_profiles_config = workspace_config.get('character_profiles', {})
        if character_profiles_config and character_profiles_config.get('enabled'):
            primary_character = character_profiles_config.get('primary_character', {})
            if primary_character:
                character_profile_id = primary_character.get('character_id')
                character_description = _build_character_description(primary_character)
                logger.info(f"  Character consistency enabled: {character_profile_id}")
                logger.debug(f"    Identity anchor: {character_description}")

    # Step 09.6/09.7: Determine video style mode (faceless vs character_based)
    video_style_mode = "character_based"  # Default
    ai_selected_format = None
    format_rationale = None

    if workspace_config:
        video_style_config = workspace_config.get('video_style_mode', {})
        video_style_mode = video_style_config.get('type', 'character_based')

        if video_style_mode == 'faceless':
            # Step 09.7: AI-driven format selection (once per video for consistency)
            ai_style_preferences = video_style_config.get('ai_style_preferences', {})
            vertical_id = workspace_config.get('vertical_id', 'general')

            ai_selected_format, format_rationale = _select_ai_visual_format(
                script=script,
                plan=plan,
                ai_style_preferences=ai_style_preferences,
                vertical_id=vertical_id
            )

            logger.info(f"  Video style: FACELESS mode ({ai_selected_format})")
            logger.debug(f"    Rationale: {format_rationale}")
        else:
            logger.info(f"  Video style: CHARACTER-BASED mode")

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
        # ENHANCED: AI-Driven Cinematic Prompt Engine with Sora 2 best practices
        logger.info(f"  Using scene_voiceover_map ({len(script.scene_voiceover_map)} content scenes)")
        logger.info(f"  🎬 AI-Enhanced Cinematic Prompt Engine activated")
        logger.info(f"  🤖 LLM will generate creative prompts with full workspace context")

        # Extract parameters for cinematic system
        series_format_name = series_format.name if series_format else "tutorial"
        vertical_id = workspace_config.get('vertical_id', 'education') if workspace_config else 'education'
        total_scenes = len(script.scene_voiceover_map)

        # Step 10: Check if single long video mode is enabled (for character consistency)
        use_single_long_video = False
        if workspace_config:
            video_style_config = workspace_config.get('video_style_mode', {})
            use_single_long_video = video_style_config.get('use_single_long_video', False)

        if use_single_long_video:
            # Step 10: SINGLE LONG VIDEO MODE - Generate one continuous video
            # This ensures character consistency by using a single Sora/Veo generation
            logger.info("  🎭 SINGLE LONG VIDEO MODE activated (for character consistency)")
            logger.info(f"  Consolidating {total_scenes} scenes into ONE continuous video")

            # Consolidate all scene voiceover texts
            full_narrative = " ".join([scene.voiceover_text for scene in script.scene_voiceover_map])
            total_duration = sum([scene.est_duration_seconds for scene in script.scene_voiceover_map])

            # Limit to maximum 30 seconds for Sora 2
            if total_duration > 30:
                logger.warning(f"  Total duration {total_duration}s exceeds 30s limit, capping at 30s")
                total_duration = 30

            logger.info(f"  Combined duration: {total_duration}s")
            logger.info(f"  Narrative length: {len(full_narrative)} characters")

            # Generate comprehensive prompt for single long video
            result = _generate_ai_enhanced_scene_prompt(
                segment_name="full_narrative",
                segment_text=full_narrative,
                plan=plan,
                scene_index=0,
                total_scenes=1,  # Single scene mode
                series_format_name=series_format_name,
                vertical_id=vertical_id,
                ai_format="character_based" if video_style_mode == "character_based" else ai_selected_format,
                brand_manual=brand_manual if brand_manual else {},
                brand_tone=workspace_config.get('brand_tone', '') if workspace_config else '',
                narrator_persona=workspace_config.get('narrator_persona') if workspace_config else None,
                target_language=workspace_config.get('target_language', 'en') if workspace_config else 'en',
                recent_titles=workspace_config.get('recent_titles', []) if workspace_config else [],
                previous_scene_composition=None,  # No previous scene in single video mode
                character_description=character_description if character_description else None,
                video_style_mode=video_style_mode
            )
            veo_prompt = result['prompt']

            # Step 10: Append instructions for continuous shot with dynamic camera and NO audio
            veo_prompt += "\n\nIMPORTANT: This is a single continuous shot. Maintain the SAME character, location, and visual identity throughout the entire video. NO scene cuts or transitions."

            # Step 10: CRITICAL - Prevent Sora from generating audio/narration
            veo_prompt += "\n\nCRITICAL: SILENT VIDEO - NO AUDIO, NO NARRATION, NO SPEECH. Audio will be added separately in post-production."

            # Step 10: Add dynamic camera movement instructions for visual variety
            veo_prompt += f"\n\nCINEMATIC PROGRESSION ({int(total_duration)}s continuous shot):"
            veo_prompt += "\n• 0-10s: Wide establishing shot with slow push-in to reveal subject"
            veo_prompt += "\n• 10-20s: Medium shot with subtle camera orbit for depth and dimension"
            veo_prompt += "\n• 20-30s: Close-up with dynamic framing shift to emphasize key moment"
            veo_prompt += "\nMAINTAIN consistent character appearance, location, and lighting throughout all camera movements."

            # Create single comprehensive scene
            single_scene = VisualScene(
                scene_id=1,
                prompt_for_veo=veo_prompt,
                est_duration_seconds=total_duration,
                voiceover_text=full_narrative,
                segment_type="full_narrative"
            )
            scenes.append(single_scene)

            logger.info(f"  ✓ Single long video scene created: {total_duration}s")
            logger.debug(f"    Narrative preview: {full_narrative[:100]}...")

        else:
            # MULTI-SCENE MODE (original behavior)
            # Track composition for spatial continuity across scenes
            previous_scene_composition = None

            for scene_index, scene_vo in enumerate(script.scene_voiceover_map):
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

                # Generate cinematic Veo prompt for this scene
                # NEW: Cinematic Prompt Engine integrates:
                # - Shot type progression (wide/medium/close variety)
                # - Camera movement choreography
                # - Lighting design per vertical
                # - Audio cues generation
                # - 7-layer prompt structure
                # - Content-specific descriptions

                # Special handling for hook scene (first content scene)
                if segment_name == "hook" and video_style_mode == 'faceless':
                    # Optimize hook for maximum impact retention
                    palette = brand_manual.get('color_palette', {}) if brand_manual else {}
                    brand_colors = {
                        'primary': palette.get('primary', '#1976D2'),
                        'secondary': palette.get('secondary', '#4CAF50'),
                        'accent': palette.get('accent', '#FFC107')
                    }
                    veo_prompt = _optimize_hook_scene(
                        hook_text=scene_vo.voiceover_text,
                        plan=plan,
                        ai_format=ai_selected_format,
                        brand_colors=brand_colors,
                        vertical_id=vertical_id
                    )
                elif video_style_mode == 'faceless':
                    # Use AI-enhanced prompt generator with FULL workspace context and spatial continuity
                    result = _generate_ai_enhanced_scene_prompt(
                        segment_name=segment_name,
                        segment_text=scene_vo.voiceover_text,
                        plan=plan,
                        scene_index=scene_index,
                        total_scenes=total_scenes,
                        series_format_name=series_format_name,
                        vertical_id=vertical_id,
                        ai_format=ai_selected_format,
                        brand_manual=brand_manual if brand_manual else {},
                        brand_tone=workspace_config.get('brand_tone', '') if workspace_config else '',
                        narrator_persona=workspace_config.get('narrator_persona') if workspace_config else None,
                        target_language=workspace_config.get('target_language', 'en') if workspace_config else 'en',
                        recent_titles=workspace_config.get('recent_titles', []) if workspace_config else [],
                        previous_scene_composition=previous_scene_composition  # Spatial continuity
                    )
                    # Extract prompt and update composition for next scene
                    veo_prompt = result['prompt']
                    previous_scene_composition = result['composition']
                else:
                    # Use AI-enhanced prompt generator for CHARACTER-BASED mode
                    # Now includes Energy Orchestration + Spatial Continuity!
                    result = _generate_ai_enhanced_scene_prompt(
                        segment_name=segment_name,
                        segment_text=scene_vo.voiceover_text,
                        plan=plan,
                        scene_index=scene_index,
                        total_scenes=total_scenes,
                        series_format_name=series_format_name,
                        vertical_id=vertical_id,
                        ai_format="character_based",  # Mark as character mode
                        brand_manual=brand_manual if brand_manual else {},
                        brand_tone=workspace_config.get('brand_tone', '') if workspace_config else '',
                        narrator_persona=workspace_config.get('narrator_persona') if workspace_config else None,
                        target_language=workspace_config.get('target_language', 'en') if workspace_config else 'en',
                        recent_titles=workspace_config.get('recent_titles', []) if workspace_config else [],
                        previous_scene_composition=previous_scene_composition,  # Spatial continuity
                        character_description=character_description,  # Character identity anchor
                        video_style_mode="character_based"  # Mode flag
                    )
                    # Extract prompt and update composition for next scene
                    veo_prompt = result['prompt']
                    previous_scene_composition = result['composition']

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
            # Step 09: Pass brand_manual for color palette enforcement and visual_context for recurring scenarios
            # Step 09.5: Pass character_description for character consistency
            # Step 09.6/09.7: Route to faceless (AI-driven format) or character-based prompt generation
            if video_style_mode == 'faceless':
                veo_prompt = _generate_faceless_prompt(segment_name, segment_text, plan, visual_style, ai_format=ai_selected_format, brand_manual=brand_manual)
            else:
                veo_prompt = _generate_veo_prompt(segment_name, segment_text, plan, visual_style, brand_manual=brand_manual, visual_context=visual_context, character_description=character_description)

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
    # Step 09: Include visual context tracking for analytics
    # Step 09.6: Include video_style_mode tracking
    # Step 09.7: Include AI-selected format tracking for faceless videos
    visual_plan = VisualPlan(
        aspect_ratio="9:16",  # YouTube Shorts vertical format
        style_notes=visual_style,
        scenes=scenes,
        visual_context_id=visual_context.get('context_id') if visual_context else None,
        visual_context_name=visual_context.get('name') if visual_context else None,
        character_profile_id=character_profile_id,  # Step 09.5: Character consistency tracking
        character_description=character_description,  # Step 09.5: Persistent identity anchor
        video_style_mode=video_style_mode,  # Step 09.6: Faceless vs character-based tracking
        ai_selected_format=ai_selected_format,  # Step 09.7: AI format selection
        format_rationale=format_rationale  # Step 09.7: Why this format was chosen
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
