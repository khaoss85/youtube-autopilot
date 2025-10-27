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
            # Step 09: Pass brand_manual for color palette enforcement and visual_context for recurring scenarios
            # Step 09.5: Pass character_description for character consistency
            # Step 09.6/09.7: Route to faceless (AI-driven format) or character-based prompt generation
            if video_style_mode == 'faceless':
                veo_prompt = _generate_faceless_prompt(
                    segment_name,
                    scene_vo.voiceover_text,
                    plan,
                    visual_style,
                    ai_format=ai_selected_format,
                    brand_manual=brand_manual
                )
            else:
                veo_prompt = _generate_veo_prompt(
                    segment_name,
                    scene_vo.voiceover_text,
                    plan,
                    visual_style,
                    brand_manual=brand_manual,
                    visual_context=visual_context,
                    character_description=character_description
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
