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
from yt_autopilot.agents.cinematographer import get_cinematic_specs


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
# Phase B1: Cinematography functions extracted to cinematographer.py
# Use get_cinematic_specs() from cinematographer for all cinematography needs


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
    # Phase B1: Use cinematographer for all cinematic specifications
    cinematic_specs = get_cinematic_specs(
        scene_index=scene_index,
        segment_name=segment_name,
        series_format_name=series_format_name,
        vertical_id=vertical_id,
        ai_format=ai_format,
        total_scenes=total_scenes
    )

    # Extract individual elements from cinematographer result
    shot_specs = {
        'shot': cinematic_specs['shot_type'],
        'lens': cinematic_specs['lens'],
        'purpose': cinematic_specs['purpose']
    }
    camera_movement = cinematic_specs['camera_movement']
    lighting = cinematic_specs['lighting']
    audio_cues = cinematic_specs['audio_cues']

    # Build emotional context from cinematographer result
    emotional_context = {
        'energy_level': cinematic_specs['energy_level'],
        'story_beat': cinematic_specs['story_beat'],
        'pacing_note': cinematic_specs['pacing_note']
    }

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

ADDITIONALLY (Phase B1 - AI-Driven Post-Production Planning):
Analyze the voiceover content and plan:

**TEXT OVERLAYS** (Best Practice: Overlays enhance mobile viewing and retention):
- Identify numbers, stats, percentages that deserve visual emphasis
- Identify key points to display as text (for mobile/no-audio viewing)
- If this is a CTA scene, suggest visual call-to-action overlay
- For each overlay specify: text, timing_start (seconds from scene start), timing_duration (seconds), position (top_center/center/bottom_center/etc), style (bold/subtle/animated), purpose (stat/key_point/cta/subtitle)

**B-ROLL INSERTIONS** (Best Practice: B-roll adds variety and supports message):
- Identify moments where B-roll would enhance engagement or provide visual proof
- Suggest B-roll for: data visualization (charts/graphs), product demos, visual evidence, engagement breaks in long scenes
- For each B-roll specify: timing_start (seconds), timing_duration (seconds), description (what B-roll to show), source_type (stock/graphic/screen_recording/animation), purpose (data_viz/engagement_break/visual_proof)

RULES FOR AI PLANNING:
- If voiceover has numbers/stats → suggest overlay to emphasize them
- If scene is >8 seconds → consider B-roll for variety
- If scene describes data/trends → suggest chart/graph B-roll
- If scene is demo/tutorial → suggest screen recording B-roll
- If scene is hook → use animated overlays for maximum impact
- If scene is CTA (outro) → suggest visual call-to-action overlay
- For mobile viewing: prioritize subtitles/overlays for key points
- NO overlays if scene is too short (<3 seconds)
- Be selective: quality over quantity

EXAMPLE (for reference):
Voiceover: "Bitcoin ha raggiunto $67,000 questa settimana, +15% in 7 giorni."
Scene duration: 6 seconds

text_overlays: [
  {{"text": "$67,000", "timing_start": 1, "timing_duration": 2, "position": "top_center", "style": "bold", "purpose": "stat"}},
  {{"text": "+15% 📈", "timing_start": 3, "timing_duration": 2, "position": "center", "style": "animated", "purpose": "stat"}}
]

broll_notes: [
  {{"timing_start": 2, "timing_duration": 4, "description": "Animated chart showing Bitcoin price rising from $58k to $67k over 7 days with green upward trend line", "source_type": "graphic", "purpose": "data_viz"}}
]

OUTPUT FORMAT (JSON):
{{
  "veo_prompt": "<your 300-500 char cinematic prompt>",
  "text_overlays": [
    {{"text": "<text>", "timing_start": <int>, "timing_duration": <int>, "position": "<position>", "style": "<style>", "purpose": "<purpose>"}}
  ],
  "broll_notes": [
    {{"timing_start": <int>, "timing_duration": <int>, "description": "<description>", "source_type": "<type>", "purpose": "<purpose>"}}
  ]
}}

⚠️ CRITICAL: Respond with VALID JSON ONLY. No explanations before or after."""

    # Step 4: Call LLM with error handling
    try:
        from yt_autopilot.services.llm_router import generate_text

        logger.debug(f"  🤖 Calling LLM for AI-enhanced scene {scene_index + 1} prompt...")

        response = generate_text(
            role="cinematographer",
            task=llm_prompt,
            context="",  # Context is in task
            style_hints={"temperature": 0.7, "response_format": "json"}  # Request JSON
        )

        # Parse JSON response (Phase B1: Extract prompt + overlays + B-roll)
        import json
        import re

        # Clean response (remove markdown code blocks if present)
        response_clean = response.strip()
        if response_clean.startswith('```'):
            response_clean = re.sub(r'^```(?:json)?\s*\n', '', response_clean)
            response_clean = re.sub(r'\n```\s*$', '', response_clean)

        try:
            llm_result = json.loads(response_clean)
            prompt = llm_result.get('veo_prompt', response_clean)  # Fallback to full response if no veo_prompt

            # Parse text overlays (AI-generated)
            text_overlays = []
            if 'text_overlays' in llm_result and isinstance(llm_result['text_overlays'], list):
                from yt_autopilot.core.schemas import TextOverlay
                for overlay_data in llm_result['text_overlays']:
                    try:
                        text_overlays.append(TextOverlay(
                            text=overlay_data['text'],
                            timing_start=overlay_data['timing_start'],
                            timing_duration=overlay_data['timing_duration'],
                            position=overlay_data['position'],
                            style=overlay_data['style'],
                            purpose=overlay_data['purpose']
                        ))
                    except Exception as e:
                        logger.debug(f"    Skipping invalid overlay: {e}")

            # Parse B-roll notes (AI-generated)
            broll_notes = []
            if 'broll_notes' in llm_result and isinstance(llm_result['broll_notes'], list):
                from yt_autopilot.core.schemas import BRollNote
                for broll_data in llm_result['broll_notes']:
                    try:
                        broll_notes.append(BRollNote(
                            timing_start=broll_data['timing_start'],
                            timing_duration=broll_data['timing_duration'],
                            description=broll_data['description'],
                            source_type=broll_data['source_type'],
                            purpose=broll_data['purpose']
                        ))
                    except Exception as e:
                        logger.debug(f"    Skipping invalid B-roll note: {e}")

            logger.info(f"  ✓ AI-enhanced prompt generated for scene {scene_index + 1} ({len(prompt)} chars)")
            logger.info(f"    AI planned: {len(text_overlays)} text overlays, {len(broll_notes)} B-roll insertions")

        except json.JSONDecodeError as e:
            logger.warning(f"  ⚠️ Could not parse JSON from LLM (using response as prompt): {e}")
            prompt = response_clean
            text_overlays = []
            broll_notes = []

        # Build composition info for next scene's spatial continuity
        current_composition = {
            'shot': shot_specs['shot'],
            'setting': f"{ai_format} virtual environment",
            'spatial_anchor': f"{lighting['mood']} lit {ai_format} space with {colors['primary']} tones"
        }

        return {
            'prompt': prompt,
            'composition': current_composition,
            'text_overlays': text_overlays,  # Phase B1: AI-planned overlays
            'broll_notes': broll_notes  # Phase B1: AI-planned B-roll
        }

    except Exception as e:
        logger.warning(f"  ⚠️ AI prompt generation failed for scene {scene_index + 1}: {e}")
        logger.info(f"  → Falling back to deterministic prompt generation")

        # Phase B1: Log fallback for overlay/B-roll planning failure
        from yt_autopilot.core.logger import log_fallback
        log_fallback(
            component="VISUAL_PLANNER",
            fallback_type="DETERMINISTIC_PROMPT_NO_OVERLAYS",
            reason=f"LLM failed to generate prompt with overlays/B-roll: {e}",
            impact="MEDIUM"
        )

        # Step 5: Fallback to deterministic system using cinematographer's cinematic prompt
        # Phase B1: Cinematographer already built the prompt, we can use it directly
        from yt_autopilot.agents.cinematographer import build_cinematic_prompt

        fallback_prompt = build_cinematic_prompt(
            cinematic_specs=cinematic_specs,
            brand_colors=colors,
            ai_format=ai_format,
            segment_text=segment_text,
            video_style_mode=video_style_mode,
            topic=plan.working_title
        )

        # Build composition info for next scene (same as success path)
        current_composition = {
            'shot': shot_specs['shot'],
            'setting': f"{ai_format} virtual environment",
            'spatial_anchor': f"{lighting['mood']} lit {ai_format} space with {colors['primary']} tones"
        }

        # Phase B1: Return empty arrays for overlays/B-roll (no AI planning available)
        return {
            'prompt': fallback_prompt,
            'composition': current_composition,
            'text_overlays': [],  # Empty - fallback has no overlay planning
            'broll_notes': []  # Empty - fallback has no B-roll planning
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
    workspace_config: Optional[Dict] = None,
    duration_strategy: Optional[Dict] = None,
    timeline: Optional['Timeline'] = None  # Phase C - P2.2: Single source of truth
) -> VisualPlan:
    """
    Generates a complete visual plan with scene-by-scene prompts for Veo.

    This is the entry point for the VisualPlanner agent. It:
    - Syncs visual scenes with script's scene_voiceover_map (Step 07.3)
    - Creates Veo-compatible generation prompts for each scene
    - Embeds voiceover text into each scene for precise sync
    - Applies channel's visual style consistently
    - Adapts format based on duration strategy (short/mid/long)

    Step 07.3: Now uses script.scene_voiceover_map for precise audio/visual sync.
    Falls back to legacy scene segmentation if scene_voiceover_map is empty.

    Step 07.5: Format engine - adds intro/outro scenes and tags with segment_type.
    If series_format is provided, creates intro/outro scenes from template.

    Step 09: Color palette enforcement from visual_brand_manual.
    If workspace_config contains visual_brand_manual with color palette,
    enforces those colors in Veo prompts.

    MONETIZATION REFACTOR: Now adapts to duration strategy:
    - Short-form (<60s): 9:16 vertical
    - Mid-form (60s-8min): 16:9 horizontal or mixed
    - Long-form (8+min): 16:9 horizontal with more scenes

    Phase C - P2.2: Now uses Timeline.reconciled_duration as single source of truth.
    If timeline provided, uses timeline.reconciled_duration (overrides duration_strategy).

    Args:
        plan: Video plan with topic and context
        script: Complete video script (with scene_voiceover_map in Step 07.3+)
        memory: Channel memory dict containing visual_style
        series_format: Optional series format template for intro/outro (Step 07.5)
        workspace_config: Optional workspace configuration with visual_brand_manual (Step 09)
        duration_strategy: Optional duration strategy from Duration Strategist (DEPRECATED if timeline provided)
        timeline: Phase C - P2.2 - Timeline object with reconciled_duration (single source of truth)

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

    # MONETIZATION REFACTOR: Determine aspect ratio and scaling from duration strategy
    # Phase C - P2.2: Use Timeline.reconciled_duration as single source of truth
    format_type = "short"  # Default fallback
    target_duration_seconds = 60  # Default fallback
    aspect_ratio = "9:16"  # Default Shorts format
    duration_source = "default_fallback"

    if timeline:
        # Phase C - P2.2: Timeline takes precedence
        target_duration_seconds = timeline.reconciled_duration
        format_type = timeline.format_type
        aspect_ratio = timeline.aspect_ratio
        duration_source = "Timeline.reconciled_duration"
        logger.info(f"  Using Timeline: {target_duration_seconds}s, format={format_type}, aspect={aspect_ratio}")
    elif duration_strategy:
        format_type = duration_strategy.get('format_type', 'short')
        target_duration_seconds = duration_strategy.get('target_duration_seconds', 60)
        duration_source = "duration_strategy (fallback)"

        # Aspect ratio based on format type
        if format_type == 'long':
            aspect_ratio = "16:9"  # Horizontal for long-form
            logger.info(f"  Long-form detected ({target_duration_seconds}s) → Using 16:9 horizontal")
        elif format_type == 'mid' and target_duration_seconds > 180:
            aspect_ratio = "16:9"  # Mid-form >3min also horizontal
            logger.info(f"  Mid-form >3min ({target_duration_seconds}s) → Using 16:9 horizontal")
        else:
            aspect_ratio = "9:16"  # Short/quick mid-form stays vertical
            logger.info(f"  Short/mid-form ({target_duration_seconds}s) → Using 9:16 vertical")
    else:
        logger.warning("  Duration strategy not provided, defaulting to Shorts (9:16, 60s)")

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
            prompt_for_ai_tool=series_format.intro_veo_prompt,
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

            # Apply duration limits based on format type (Fase 1-BIS-2: Monetization-aware capping)
            format_type = duration_strategy.get('format_type', 'short') if duration_strategy else 'short'

            if format_type == 'short':
                max_duration = 60  # YouTube Shorts limit
            elif format_type == 'mid':
                max_duration = 480  # 8 minutes for mid-roll ads
            elif format_type == 'long':
                max_duration = 1200  # 20 minutes max
            else:
                max_duration = 60  # Fallback to shorts

            if total_duration > max_duration:
                logger.warning(f"  Total duration {total_duration}s exceeds {format_type} format limit ({max_duration}s), capping")
                total_duration = max_duration
            else:
                logger.info(f"  Total duration {total_duration}s within {format_type} format limit ({max_duration}s)")

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
                prompt_for_ai_tool=veo_prompt,
                est_duration_seconds=total_duration,
                voiceover_text=full_narrative,
                segment_type="full_narrative",
                text_overlays=result.get('text_overlays', []),  # Phase B1: AI-planned overlays
                broll_notes=result.get('broll_notes', [])  # Phase B1: AI-planned B-roll
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
                # Phase B1: Include AI-planned overlays and B-roll from result
                scene = VisualScene(
                    scene_id=scene_vo.scene_id,
                    prompt_for_ai_tool=veo_prompt,
                    est_duration_seconds=scene_vo.est_duration_seconds,
                    voiceover_text=scene_vo.voiceover_text,  # Sync with script!
                    segment_type=segment_name,  # Step 07.5: Tag with segment type
                    text_overlays=result.get('text_overlays', []),  # Phase B1: AI-planned overlays
                    broll_notes=result.get('broll_notes', [])  # Phase B1: AI-planned B-roll
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
                prompt_for_ai_tool=veo_prompt,
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
            prompt_for_ai_tool=series_format.outro_veo_prompt,
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
    # MONETIZATION REFACTOR: Scale scene durations to match target if needed
    actual_duration = sum(scene.est_duration_seconds for scene in scenes)
    if duration_strategy and abs(actual_duration - target_duration_seconds) > target_duration_seconds * 0.2:
        # Duration mismatch > 20%, scale proportionally
        scale_factor = target_duration_seconds / actual_duration
        logger.info(f"  Scaling scene durations: {actual_duration}s → {target_duration_seconds}s (factor: {scale_factor:.2f})")

        for scene in scenes:
            original_duration = scene.est_duration_seconds
            scaled_duration = max(3, int(scene.est_duration_seconds * scale_factor))  # Min 3s per scene
            scene.est_duration_seconds = scaled_duration
            logger.debug(f"    Scene {scene.scene_id}: {original_duration}s → {scaled_duration}s")

        actual_duration_after = sum(scene.est_duration_seconds for scene in scenes)
        logger.info(f"  ✓ Scenes scaled to {actual_duration_after}s (target: {target_duration_seconds}s)")

    # Step 09.6: Include video_style_mode tracking
    # Step 09.7: Include AI-selected format tracking for faceless videos
    visual_plan = VisualPlan(
        aspect_ratio=aspect_ratio,  # MONETIZATION REFACTOR: Dynamic based on format
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
