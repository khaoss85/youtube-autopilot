"""
Cinematographer Agent: Pure cinematography design (camera, lighting, audio, emotion).

Phase B1: Extracted from visual_planner.py for separation of concerns.

Responsibilities:
- Shot type selection and progression
- Camera movement choreography
- Lighting design per vertical
- Audio cues generation
- Emotional context mapping for retention
- 7-layer cinematic prompt construction

NOT Responsible For (handled elsewhere):
- Text overlay planning (AI-driven in visual_planner)
- B-roll planning (AI-driven in visual_planner)
- AI-enhanced scene prompts (LLM-generated in visual_planner)

Author: YT Autopilot Team
Version: 1.0 (Phase B1)
"""

from typing import List, Dict, Optional
from yt_autopilot.core.logger import logger


# ==============================================================================
# SHOT TYPE & CAMERA MOVEMENT
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


# ==============================================================================
# LIGHTING DESIGN
# ==============================================================================

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


# ==============================================================================
# AUDIO CUES
# ==============================================================================

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


# ==============================================================================
# EMOTIONAL CONTEXT (RETENTION OPTIMIZATION)
# ==============================================================================

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


# ==============================================================================
# 7-LAYER CINEMATIC PROMPT BUILDING
# ==============================================================================

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


# ==============================================================================
# PUBLIC API
# ==============================================================================

def get_cinematic_specs(
    scene_index: int,
    segment_name: str,
    series_format_name: str,
    vertical_id: str,
    ai_format: str,
    total_scenes: int
) -> Dict:
    """
    Returns complete cinematographic specifications for a scene.

    This is the public API for the Cinematographer agent.
    Returns all cinematic elements needed by visual planning.

    NOTE: This function does NOT plan overlays or B-roll - those are
    handled by AI-driven LLM prompts in the visual_planner.

    Args:
        scene_index: Scene position (0-based)
        segment_name: Segment type (hook, content_X, outro, etc.)
        series_format_name: Format name (tutorial, how_to, news_flash)
        vertical_id: Content vertical (finance, tech_ai, fitness, gaming)
        ai_format: Visual format (animated_infographics, etc.)
        total_scenes: Total number of scenes in video

    Returns:
        Dict with:
        - shot_type: str (wide/medium/close)
        - lens: str (24mm, 50mm, 85mm)
        - purpose: str (shot purpose description)
        - camera_movement: str (push in, dolly, zoom, static)
        - lighting: Dict (mood, primary, direction, intensity, accents)
        - audio_cues: str (audio design description)
        - energy_level: str (HIGH, BUILDING, PEAK, RELEASE, CALL_ACTION)
        - story_beat: str (GRABBER, TENSIONE, RIVELAZIONE, SOLUZIONE, CTA)
        - pacing_note: str (retention pacing guidance)

    Example:
        >>> specs = get_cinematic_specs(
        ...     scene_index=0,
        ...     segment_name="hook",
        ...     series_format_name="tutorial",
        ...     vertical_id="finance",
        ...     ai_format="animated_infographics",
        ...     total_scenes=5
        ... )
        >>> print(specs['shot_type'])
        'wide'
        >>> print(specs['energy_level'])
        'HIGH'
    """
    shot_specs = _select_shot_type(scene_index, series_format_name)
    camera_movement = _select_camera_movement(segment_name)
    lighting = _get_lighting_design(vertical_id)
    audio_cues = _generate_audio_cues(segment_name, ai_format, vertical_id)
    emotional = _get_emotional_context(segment_name, scene_index, total_scenes)

    return {
        'shot_type': shot_specs['shot'],
        'lens': shot_specs['lens'],
        'purpose': shot_specs['purpose'],
        'camera_movement': camera_movement,
        'lighting': lighting,
        'audio_cues': audio_cues,
        'energy_level': emotional['energy_level'],
        'story_beat': emotional['story_beat'],
        'pacing_note': emotional['pacing_note']
    }


def build_cinematic_prompt(
    cinematic_specs: Dict,
    brand_colors: Dict,
    ai_format: str,
    segment_text: str,
    video_style_mode: str = "faceless",
    topic: str = "content"
) -> str:
    """
    Builds a 7-layer cinematic prompt from cinematic specifications.

    This is a public API for building prompts from cinematic_specs dict.
    Used by visual_planner fallback path when LLM generation fails.

    Args:
        cinematic_specs: Dict from get_cinematic_specs() with all cinematic elements
        brand_colors: Dict with primary, secondary, accent, background color codes
        ai_format: Visual format (animated_infographics, kinetic_typography, etc.)
        segment_text: Scene voiceover text for content description
        video_style_mode: "faceless" or "character_based"
        topic: Video topic for context

    Returns:
        7-layer cinematic prompt string optimized for Sora 2/Veo

    Example:
        >>> specs = get_cinematic_specs(0, "hook", "tutorial", "finance", "animated_infographics", 5)
        >>> colors = {'primary': '#1976D2', 'secondary': '#4CAF50', 'accent': '#FFC107', 'background': '#263238'}
        >>> prompt = build_cinematic_prompt(specs, colors, "animated_infographics", "Bitcoin hits $67k", "faceless", "Crypto trends")
        >>> print(prompt)
        'Wide shot showing: Bitcoin hits $67k...'
    """
    # Build scene_context dict
    scene_context = {
        'topic': topic,
        'duration': 0,  # Not used in prompt building
        'segment_name': 'content'
    }

    # Build cinematic_specs_internal dict (compatible with _build_7layer_cinematic_prompt)
    cinematic_specs_internal = {
        'shot': cinematic_specs['shot_type'],
        'lens': cinematic_specs['lens'],
        'purpose': cinematic_specs['purpose'],
        'camera_movement': cinematic_specs['camera_movement'],
        'lighting': cinematic_specs['lighting']
    }

    # Build brand_identity dict
    brand_identity = {
        'colors': brand_colors,
        'format': ai_format,
        'mode': video_style_mode
    }

    # Build emotional_context dict
    emotional_context = {
        'energy_level': cinematic_specs['energy_level'],
        'story_beat': cinematic_specs['story_beat'],
        'pacing_note': cinematic_specs['pacing_note']
    }

    # Call internal 7-layer builder
    return _build_7layer_cinematic_prompt(
        scene_context=scene_context,
        cinematic_specs=cinematic_specs_internal,
        audio_design=cinematic_specs['audio_cues'],
        brand_identity=brand_identity,
        ai_format=ai_format,
        segment_text=segment_text,
        emotional_context=emotional_context
    )
