"""
Narrative Arc Architect Agent: AI-driven emotional storytelling for retention.

This agent creates story structures with personality, emotional beats, and
retention hooks instead of generic template-based scripts.

Key Features:
- Emotional story arc (hook → agitation → solution → payoff)
- Voice personality injection (confident educator, empathetic friend, etc.)
- Pattern interrupts for retention
- Cliffhangers and open loops
- Proper punctuation and pacing

Replaces: Generic LLM script generation with strategic narrative design.
"""

from typing import Dict, Any, List, Optional
from yt_autopilot.services.llm_router import generate_text
from yt_autopilot.core.logger import logger, log_fallback
from yt_autopilot.core.schemas import Timeline


def design_narrative_arc(
    topic: str,
    target_duration_seconds: int,
    workspace_config: Dict[str, Any],
    duration_strategy: Dict[str, Any],
    editorial_decision: Dict[str, Any],
    bullet_count_constraint: Optional[int] = None,  # FASE 1: Quality retry constraint
    llm_generate_fn: callable = None,  # WEEK 2 Task 2.1: Language-validated LLM wrapper
    timeline: Optional[Timeline] = None  # PHASE C - P2: Single source of truth for duration
) -> Dict[str, Any]:
    """
    AI-driven narrative arc design for emotional retention optimization.

    Creates a story structure with:
    - Hook: Pattern interrupt, open loop, emotional trigger (0-3s)
    - Agitation: Pain points, problem exploration (build tension)
    - Solution: Insights, revelations, payoff (release tension)
    - CTA: Specific engagement action (not generic "follow us")

    Also includes:
    - Voice personality (matches brand tone)
    - Pattern interrupts every 8-12 seconds
    - Cliffhangers between sections
    - Proper punctuation and pacing marks

    Phase C - P2: Now uses Timeline object as single source of truth for duration.
    If timeline provided, uses timeline.reconciled_duration (overrides target_duration_seconds).

    Args:
        topic: Video topic/title
        target_duration_seconds: Target video duration (DEPRECATED if timeline provided)
        workspace_config: Brand tone, style, personality
        duration_strategy: Output from Duration Strategist
        editorial_decision: Editorial strategy context
        bullet_count_constraint: FASE 1 - If provided, force exactly this many content acts (quality retry)
        llm_generate_fn: WEEK 2 Task 2.1 - Language-validated LLM wrapper (uses generate_text if None)
        timeline: PHASE C - P2 - Timeline object with reconciled_duration (single source of truth)

    Returns:
        Dict with:
        - narrative_structure: List[Dict] (acts with emotional beats)
        - voice_personality: str (narrator personality description)
        - retention_hooks: List[str] (pattern interrupts, cliffhangers)
        - full_voiceover: str (complete script with punctuation)
        - emotional_beats: List[Dict] (timestamp → emotion mapping)
        - pacing_notes: str (delivery guidance)

    Example:
        >>> arc = design_narrative_arc(
        ...     topic="$6.5M margin call disaster",
        ...     target_duration_seconds=420,  # Ignored if timeline provided
        ...     workspace_config=workspace,
        ...     duration_strategy=duration_strategy,
        ...     editorial_decision=editorial,
        ...     bullet_count_constraint=6,  # FASE 1: Force 6 content acts
        ...     timeline=timeline  # PHASE C - P2: Single source of truth
        ... )
        >>> print(arc['voice_personality'])  # "Confident financial educator"
        >>> print(arc['full_voiceover'][:100])  # Hook with personality
    """
    # Phase C - P2: Use Timeline.reconciled_duration as single source of truth
    if timeline:
        actual_duration = timeline.reconciled_duration
        duration_source = "Timeline.reconciled_duration"
    else:
        actual_duration = target_duration_seconds
        duration_source = "target_duration_seconds (fallback)"

    logger.info("Narrative Architect designing story structure...")
    logger.info(f"  Topic: {topic}")
    logger.info(f"  Target Duration: {actual_duration}s ({actual_duration // 60}min {actual_duration % 60}s) [from {duration_source}]")

    # Extract context
    brand_tone = workspace_config.get('brand_tone', 'Professional, educational')
    format_type = duration_strategy.get('format_type', 'mid')
    content_depth_score = duration_strategy.get('content_depth_score', 0.5)
    target_language = workspace_config.get('target_language', 'en')  # WEEK 2 Task 2.1: Extract language

    angle = editorial_decision.get('angle', 'education')
    serie_concept = editorial_decision.get('serie_concept', 'Tutorial')

    # WEEK 2 Task 2.1: Use language-validated LLM if provided, fallback to direct
    generate_fn = llm_generate_fn if llm_generate_fn else generate_text

    # Construct AI prompt for narrative design
    # WEEK 2 Task 2.1: Add language mapping for explicit instruction
    language_names = {
        "en": "ENGLISH",
        "it": "ITALIAN",
        "es": "SPANISH",
        "fr": "FRENCH",
        "de": "GERMAN",
        "pt": "PORTUGUESE"
    }
    language_instruction = language_names.get(target_language.lower(), target_language.upper())

    # Calculate word count targets (Layer 1: Prevention)
    target_words_total = int(actual_duration * 2.5)  # 2.5 words/second average speaking rate
    num_acts = (bullet_count_constraint + 2) if bullet_count_constraint else 7  # Hook + content + CTA
    words_per_act = target_words_total // num_acts

    prompt = f"""You are a master storytelling architect for YouTube video retention.

⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
ALL OUTPUT MUST BE IN {language_instruction}. Every single word of voiceover must be in {language_instruction}.
DO NOT mix languages. If you see examples in other languages below, IGNORE their language and write in {language_instruction}.

TOPIC: "{topic}"
TARGET DURATION: {actual_duration}s ({actual_duration // 60}min {actual_duration % 60}s) [PHASE C - P2: From Timeline.reconciled_duration - MUST RESPECT]

⚠️ CRITICAL WORD COUNT REQUIREMENT (Layer 1: Duration Prevention) ⚠️
═══════════════════════════════════════════════════════════════════════════
TARGET WORD COUNT: {target_words_total} words total (~2.5 words/second speaking rate)

This is MANDATORY to match the {actual_duration}s duration target.

WORD COUNT DISTRIBUTION:
- Total acts: {num_acts} (Hook + {num_acts-2} content acts + CTA)
- Words per act: ~{words_per_act} words minimum
- Hook: ~{words_per_act} words
- Each Content act: ~{words_per_act} words
- CTA: ~{words_per_act} words

VERIFICATION CHECKLIST (REQUIRED BEFORE RESPONDING):
✓ 1. Count words in EACH act's voiceover field
✓ 2. Sum total words across ALL acts
✓ 3. Ensure total is {target_words_total} words ±10% ({int(target_words_total * 0.9)}-{int(target_words_total * 1.1)} words)
✓ 4. If too short → ADD more detail/examples/stories/explanations
✓ 5. If too long → BE CONCISE but don't sacrifice clarity

⚠️ FAILURE TO MEET WORD COUNT = SCRIPT VALIDATION FAILURE ⚠️
═══════════════════════════════════════════════════════════════════════════

FORMAT: {format_type} (short/mid/long)
CONTENT DEPTH: {content_depth_score:.2f} (0=thin, 1=deep)

BRAND TONE: {brand_tone[:200]}
ANGLE: {angle}
SERIE: {serie_concept}
{f'''
🔒 CRITICAL CONSTRAINT (Quality Retry):
YOU MUST create EXACTLY {bullet_count_constraint} content acts (excluding Hook and CTA).
This is a HARD REQUIREMENT from Content Depth Strategist.

Structure: Hook + {bullet_count_constraint} content acts + CTA = {bullet_count_constraint + 2} total acts
''' if bullet_count_constraint else ''}
YOUR TASK:
Design an EMOTIONAL STORY ARC that maximizes viewer retention through:

1. **HOOK (0-3 seconds)**: Pattern interrupt
   - NOT generic "Ever heard of..."
   - Open loop: tease the payoff
   - Emotional trigger: shock, curiosity, relatability
   - Example: "This trader lost $6.5M in ONE NIGHT. The mistake? Completely avoidable."

2. **AGITATION (build tension)**: Pain points
   - Explore the problem
   - Build emotional investment
   - "Here's what went wrong..."
   - Pattern interrupt mid-section: "But wait, there's a twist..."

3. **SOLUTION (release tension)**: Insights
   - Reveal the lesson
   - Provide value
   - "The truth is..."

4. **PAYOFF + CTA**: Engagement
   - Deliver on hook promise
   - Specific CTA (NOT "follow us")
   - Example: "Comment YOUR worst trade loss below!"

VOICE PERSONALITY:
Based on brand tone "{brand_tone[:100]}", choose narrator personality:
- Confident Educator (authoritative, clear)
- Empathetic Friend (relatable, supportive)
- Investigative Journalist (curious, revealing)
- Enthusiastic Guide (energetic, motivating)

RETENTION TACTICS:
- Pattern interrupts every 8-12 seconds
- Cliffhangers between acts: "But here's what REALLY happened..."
- Open loops: "In 30 seconds, I'll reveal..."
- Direct address: "You might be thinking..."
- Specific examples (not abstractions)

⚠️ DURATION ALLOCATION REQUIREMENT (Layer 1: AI-Driven Duration Prevention) ⚠️
═══════════════════════════════════════════════════════════════════════════
YOU MUST distribute {actual_duration}s across ALL acts intelligently:
- Each act's "duration_seconds" field = estimated speaking time for that voiceover
- Use word count of voiceover ÷ 2.5 = duration_seconds
- Acts should be proportional: longer content = more seconds
- Hook: typically {int(words_per_act / 2.5)}s (~{words_per_act} words)
- Each Content act: typically {int(words_per_act / 2.5)}s (~{words_per_act} words)
- CTA: typically {int(words_per_act / 2.5)}s (~{words_per_act} words)

DURATION VERIFICATION (REQUIRED):
✓ Calculate: sum of ALL duration_seconds fields must = {actual_duration}s ±10% ({int(actual_duration * 0.9)}-{int(actual_duration * 1.1)}s)
✓ Each act: duration_seconds = len(voiceover.split()) ÷ 2.5 (rounded to int)
✓ If sum is too low → ADD more voiceover content to acts
✓ If sum is too high → CONDENSE voiceover content

⚠️ FAILURE TO MATCH DURATION = PIPELINE VALIDATION FAILURE ⚠️
═══════════════════════════════════════════════════════════════════════════

RESPOND IN THIS EXACT JSON FORMAT:
{{
  "voice_personality": "<chosen personality with brief description>",
  "narrative_structure": [{f'''
    // ⚠️ CRITICAL: You MUST include EXACTLY {bullet_count_constraint} content acts (excluding Hook and CTA)
    // Structure: 1 Hook + {bullet_count_constraint} content acts + 1 Payoff_CTA
    // Total acts in this array: {bullet_count_constraint + 2}
    ''' if bullet_count_constraint else ''}
    {{
      "act_name": "Hook",
      "duration_seconds": <int - MUST match voiceover word count ÷ 2.5>,
      "emotional_beat": "<shock|curiosity|relatability>",
      "voiceover": "<script with proper punctuation - {words_per_act} words target>",
      "retention_tactic": "<pattern interrupt|open loop|etc>"
    }},{f'''
    // Now add EXACTLY {bullet_count_constraint} content acts (name them Content_1, Content_2, ... Content_{bullet_count_constraint}):
    {{
      "act_name": "Content_1",
      "duration_seconds": <int - MUST match voiceover word count ÷ 2.5>,
      "emotional_beat": "<tension|curiosity|insight|etc>",
      "voiceover": "<script - {words_per_act} words target>",
      "retention_tactic": "<specific tactic>"
    }},
    // ... repeat for Content_2, Content_3, ... Content_{bullet_count_constraint}
    {{
      "act_name": "Content_{bullet_count_constraint}",
      "duration_seconds": <int - MUST match voiceover word count ÷ 2.5>,
      "emotional_beat": "<emotion>",
      "voiceover": "<script - {words_per_act} words target>",
      "retention_tactic": "<tactic>"
    }},''' if bullet_count_constraint else '''
    {{
      "act_name": "Agitation",
      "duration_seconds": <int - MUST match voiceover word count ÷ 2.5>,
      "emotional_beat": "<tension|empathy|concern>",
      "voiceover": "<script - {words_per_act} words target>",
      "retention_tactic": "<cliffhanger|question|etc>"
    }},
    {{
      "act_name": "Solution",
      "duration_seconds": <int - MUST match voiceover word count ÷ 2.5>,
      "emotional_beat": "<relief|insight|hope>",
      "voiceover": "<script - {words_per_act} words target>",
      "retention_tactic": "<revelation|contrast|etc>"
    }},'''}
    {{
      "act_name": "Payoff_CTA",
      "duration_seconds": <int - MUST match voiceover word count ÷ 2.5>,
      "emotional_beat": "<empowerment|community>",
      "voiceover": "<script with specific CTA - {words_per_act} words target>",
      "retention_tactic": "<call to action|social proof>"
    }}
  ],
  "retention_hooks": [
    "<list of specific pattern interrupts/cliffhangers used>"
  ],
  "pacing_notes": "<delivery guidance: fast/slow sections, emphasis, pauses>",
  "emotional_journey": "<brief arc summary: start emotion → end emotion>"
}}

CRITICAL:
- Write for SPOKEN delivery (contractions, rhythm, pauses)
- Use proper punctuation (commas, periods, em-dashes, ellipses)
- NO filler words ("um", "like", "you know")
- Specific examples > abstract concepts
- ⚠️ Duration must sum to approximately {actual_duration}s (±10%) - TIMELINE CONSTRAINT MUST BE RESPECTED ⚠️
- ⚠️ WORD COUNT MUST BE {target_words_total} words ±10% ({int(target_words_total * 0.9)}-{int(target_words_total * 1.1)} words) - COUNT BEFORE RESPONDING ⚠️
{f'''
⚠️ SELF-VERIFICATION (REQUIRED BEFORE RESPONDING):
1. Count your content acts (acts that are NOT Hook or Payoff_CTA)
2. Required count: EXACTLY {bullet_count_constraint} content acts
3. Your structure should be: Hook (1) + Content acts ({bullet_count_constraint}) + Payoff_CTA (1) = {bullet_count_constraint + 2} total acts
4. If count does not match, REVISE your structure now before responding
5. Double-check: narrative_structure array must have {bullet_count_constraint + 2} objects
''' if bullet_count_constraint else ''}
⚠️ CRITICAL: YOU MUST RESPOND ONLY WITH VALID JSON ⚠️

DO NOT include any text before or after the JSON.
DO NOT use markdown code blocks.
RESPOND WITH RAW JSON ONLY.
"""

    # Call LLM for AI-driven narrative design
    # WEEK 2 Task 2.1: Use language-validated LLM wrapper (or fallback to direct)
    try:
        response = generate_fn(
            role="narrative_architect",
            task=prompt,
            context="",
            style_hints={
                "response_format": "json",
                "max_tokens": 2000,
                "language": target_language  # WEEK 2 Task 2.1: Add language hint
            }
        )

        # Parse JSON response with robust handling
        import json
        import re

        # Try direct JSON parse first
        try:
            narrative = json.loads(response)
        except json.JSONDecodeError:
            # Fallback: Extract JSON from markdown code blocks or text
            logger.warning("Direct JSON parse failed, attempting extraction...")

            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                narrative = json.loads(json_match.group(1))
                logger.info("Extracted JSON from markdown code block")
            else:
                # Try to find JSON object in text
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
                if json_match:
                    narrative = json.loads(json_match.group(0))
                    logger.info("Extracted JSON from text")
                else:
                    raise ValueError("Could not extract valid JSON from response")

        # Validate structure
        narrative.setdefault('voice_personality', 'Confident Educator')
        narrative.setdefault('narrative_structure', [])
        narrative.setdefault('retention_hooks', [])
        narrative.setdefault('pacing_notes', 'Moderate pace, clear enunciation')
        narrative.setdefault('emotional_journey', 'Curiosity → Tension → Relief → Empowerment')

        # Build full voiceover from acts
        full_voiceover = " ".join([
            act['voiceover'] for act in narrative['narrative_structure']
        ])
        narrative['full_voiceover'] = full_voiceover

        # Build emotional beats timeline
        emotional_beats = []
        cumulative_time = 0
        for act in narrative['narrative_structure']:
            emotional_beats.append({
                'timestamp': cumulative_time,
                'act': act['act_name'],
                'emotion': act['emotional_beat']
            })
            cumulative_time += act.get('duration_seconds', 0)
        narrative['emotional_beats'] = emotional_beats

        logger.info(f"✓ Narrative Arc designed:")
        logger.info(f"  Voice Personality: {narrative['voice_personality']}")
        logger.info(f"  Acts: {len(narrative['narrative_structure'])}")
        logger.info(f"  Total Duration: ~{cumulative_time}s")
        logger.info(f"  Retention Hooks: {len(narrative['retention_hooks'])}")
        logger.info(f"  Emotional Journey: {narrative['emotional_journey']}")
        logger.info(f"  Hook Preview: {narrative['narrative_structure'][0]['voiceover'][:80]}...")

        return narrative

    except Exception as e:
        logger.error(f"Narrative Architect AI failed: {e}")
        logger.warning("Falling back to basic narrative structure")

        log_fallback(
            component="NARRATIVE_ARCHITECT",
            fallback_type="BASIC_STRUCTURE",
            reason=f"LLM call failed: {e}",
            impact="HIGH"
        )

        # Fallback: Basic structure with minimal personality
        basic_hook = f"Let's talk about {topic}."
        basic_content = f"This is an important topic that affects many people. Understanding it can help you make better decisions."
        basic_cta = "Leave a comment with your thoughts below!"

        return {
            'voice_personality': 'Neutral Educator (AI fallback)',
            'narrative_structure': [
                {
                    'act_name': 'Hook',
                    'duration_seconds': 3,
                    'emotional_beat': 'curiosity',
                    'voiceover': basic_hook,
                    'retention_tactic': 'direct address'
                },
                {
                    'act_name': 'Content',
                    'duration_seconds': actual_duration - 6,
                    'emotional_beat': 'information',
                    'voiceover': basic_content,
                    'retention_tactic': 'value delivery'
                },
                {
                    'act_name': 'CTA',
                    'duration_seconds': 3,
                    'emotional_beat': 'community',
                    'voiceover': basic_cta,
                    'retention_tactic': 'call to action'
                }
            ],
            'retention_hooks': ['Direct address', 'Call to action'],
            'pacing_notes': 'Moderate pace',
            'emotional_journey': 'Neutral → Informative → Engaging',
            'full_voiceover': f"{basic_hook} {basic_content} {basic_cta}",
            'emotional_beats': [
                {'timestamp': 0, 'act': 'Hook', 'emotion': 'curiosity'},
                {'timestamp': 3, 'act': 'Content', 'emotion': 'information'},
                {'timestamp': actual_duration - 3, 'act': 'CTA', 'emotion': 'community'}
            ]
        }


def expand_narrative_voiceovers(
    narrative_arc: Dict[str, Any],
    target_duration: int,
    target_language: str,
    llm_generate_fn: callable,
    max_attempts: int = 3
) -> Dict[str, Any]:
    """
    Layer 2: AI-driven narrative expansion for duration matching.

    If narrative voiceovers are too short (>15% divergence from target),
    uses LLM to intelligently expand content while preserving emotional arc.

    This is NOT simple padding - it's semantic content enrichment:
    - Adds concrete examples and stories
    - Includes relevant statistics/data
    - Expands with relatable scenarios
    - Adds pattern interrupts for retention
    - Preserves voice personality and emotional beats

    Args:
        narrative_arc: Output from design_narrative_arc() with narrative_structure
        target_duration: Target duration in seconds
        target_language: Target language code (e.g., "it", "en")
        llm_generate_fn: LLM function for expansion
        max_attempts: Maximum expansion attempts (default: 2)

    Returns:
        Expanded narrative_arc with enriched voiceovers

    Example:
        >>> arc = design_narrative_arc(...)  # Returns 82s worth of text
        >>> expanded = expand_narrative_voiceovers(arc, 300, "it", generate_text)
        >>> # Returns 300s worth of enriched text
    """
    # Calculate current word count
    full_voiceover = narrative_arc.get('full_voiceover', '')
    current_words = len(full_voiceover.split())
    target_words = int(target_duration * 2.5)  # 2.5 words/second
    words_needed = target_words - current_words
    divergence_pct = abs(target_words - current_words) / target_words * 100 if target_words > 0 else 0

    # Only expand if divergence > 15% (Layer 2 threshold - stricter for better Gate 3 passage)
    if divergence_pct < 15:
        logger.info(f"  ✓ Narrative word count acceptable: {current_words} words vs {target_words} target ({divergence_pct:.1f}% divergence)")
        return narrative_arc

    logger.warning(f"  ⚠️ Narrative too short: {current_words} words vs {target_words} target ({divergence_pct:.1f}% divergence)")
    logger.info(f"  🔄 Layer 2: Triggering AI-driven content expansion (need +{words_needed} words, target <15% divergence)")

    from yt_autopilot.core.language_validator import LANGUAGE_NAMES

    # Track best attempt across all retries
    best_narrative_arc = narrative_arc
    best_divergence = divergence_pct
    best_words = current_words

    for attempt in range(1, max_attempts + 1):
        logger.info(f"     Expansion attempt {attempt}/{max_attempts}...")

        # Build acts list (outside f-string to avoid backslash error)
        acts_list = "\n".join([
            f"- {act['act_name']}: \"{act['voiceover']}\" ({len(act['voiceover'].split())} words)"
            for act in narrative_arc['narrative_structure']
        ])

        # Build expansion prompt
        expansion_prompt = f"""You are a content enrichment specialist for YouTube video scripts.

TASK: Expand each act's voiceover from {current_words} words total to ~{target_words} words total.

CURRENT NARRATIVE ARC:
Voice Personality: {narrative_arc.get('voice_personality', 'Unknown')}
Emotional Journey: {narrative_arc.get('emotional_journey', 'Unknown')}

CURRENT ACTS (TOO SHORT):
{acts_list}

EXPANSION REQUIREMENTS:
1. ✅ Preserve emotional arc and voice personality
2. ✅ Expand EACH act proportionally (not just one act)
3. ✅ Add depth through:
   - Concrete examples and relatable stories
   - Relevant statistics or data points (if appropriate)
   - Vivid descriptions and scenarios
   - Pattern interrupts for retention ("But here's the thing...")
   - Direct address to viewer ("You might be thinking...")
4. ✅ Maintain retention tactics (cliffhangers, open loops, etc.)
5. ✅ Keep proper punctuation and pacing for spoken delivery
6. ❌ DO NOT just repeat existing content or add filler

TARGET WORD COUNT PER ACT:
- Total target: {target_words} words
- Words per act: ~{target_words // len(narrative_arc['narrative_structure'])} words minimum

OUTPUT FORMAT (JSON):
{{
  "narrative_structure": [
    {{
      "act_name": "Hook",
      "duration_seconds": <int>,
      "emotional_beat": "<same as before>",
      "voiceover": "<EXPANDED voiceover with ~{target_words // len(narrative_arc['narrative_structure'])} words>",
      "retention_tactic": "<same or enhanced>"
    }},
    // ... repeat for ALL acts
  ]
}}

⚠️ CRITICAL VERIFICATION BEFORE RESPONDING:
1. Count words in EACH expanded voiceover
2. Sum total words
3. Ensure total is {target_words} ±10% ({int(target_words * 0.9)}-{int(target_words * 1.1)} words)
4. If still too short, add MORE detail/examples/stories

LANGUAGE: ALL voiceovers must be in {LANGUAGE_NAMES.get(target_language, target_language.upper())}

OUTPUT ONLY VALID JSON:
"""

        try:
            # Call LLM for expansion
            expanded_response = llm_generate_fn(
                role="narrative_expansion_specialist",
                task=expansion_prompt,
                context="",
                style_hints={"temperature": 0.3, "language": target_language}  # Low temp for consistency
            )

            # Parse JSON response
            import json
            import re

            # Try direct JSON parse
            try:
                expanded_data = json.loads(expanded_response)
            except json.JSONDecodeError:
                # Extract from markdown code block
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', expanded_response, re.DOTALL)
                if json_match:
                    expanded_data = json.loads(json_match.group(1))
                else:
                    # Try to find JSON object
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', expanded_response, re.DOTALL)
                    if json_match:
                        expanded_data = json.loads(json_match.group(0))
                    else:
                        raise ValueError("Could not extract JSON from LLM response")

            # Validate expansion
            if 'narrative_structure' not in expanded_data:
                raise ValueError("Missing narrative_structure in LLM response")

            # Rebuild full voiceover and calculate new word count
            expanded_voiceover = " ".join([
                act['voiceover'] for act in expanded_data['narrative_structure']
            ])
            expanded_words = len(expanded_voiceover.split())
            new_divergence = abs(target_words - expanded_words) / target_words * 100

            logger.info(f"     ✓ Expansion completed: {current_words} → {expanded_words} words")
            logger.info(f"       Divergence: {divergence_pct:.1f}% → {new_divergence:.1f}%")

            # Check if good enough or last attempt
            is_good_enough = new_divergence < 15  # Stricter threshold (was 20%)
            is_improved = new_divergence < divergence_pct
            is_last_attempt = (attempt == max_attempts)

            # Update best attempt if this is better
            if new_divergence < best_divergence:
                best_narrative_arc = {
                    'narrative_structure': expanded_data['narrative_structure'],
                    'full_voiceover': expanded_voiceover,
                    'voice_personality': narrative_arc.get('voice_personality'),
                    'emotional_journey': narrative_arc.get('emotional_journey'),
                }
                # Rebuild emotional beats
                emotional_beats = []
                cumulative_time = 0
                for act in expanded_data['narrative_structure']:
                    emotional_beats.append({
                        'timestamp': cumulative_time,
                        'act': act['act_name'],
                        'emotion': act['emotional_beat']
                    })
                    cumulative_time += act.get('duration_seconds', 0)
                best_narrative_arc['emotional_beats'] = emotional_beats
                best_divergence = new_divergence
                best_words = expanded_words

            if is_good_enough or (is_improved and is_last_attempt):
                # Success! Either hit target OR best effort on last attempt
                narrative_arc['narrative_structure'] = expanded_data['narrative_structure']
                narrative_arc['full_voiceover'] = expanded_voiceover

                # Rebuild emotional beats timeline
                emotional_beats = []
                cumulative_time = 0
                for act in narrative_arc['narrative_structure']:
                    emotional_beats.append({
                        'timestamp': cumulative_time,
                        'act': act['act_name'],
                        'emotion': act['emotional_beat']
                    })
                    cumulative_time += act.get('duration_seconds', 0)
                narrative_arc['emotional_beats'] = emotional_beats

                if is_good_enough:
                    logger.info(f"  ✅ Layer 2: AI expansion SUCCESSFUL (divergence now {new_divergence:.1f}%)")
                else:
                    logger.warning(f"  ✅ Layer 2: Accepting best attempt on final retry (divergence {new_divergence:.1f}%)")
                return narrative_arc
            else:
                # Not good enough and not last attempt - try again
                logger.warning(f"     ⚠️ Expansion attempt {attempt} insufficient (divergence {new_divergence:.1f}%), retrying...")
                current_words = expanded_words  # Use expanded as new baseline for retry
                divergence_pct = new_divergence  # Update baseline divergence

        except Exception as e:
            logger.error(f"     ❌ Expansion attempt {attempt} failed: {e}")

    # All attempts failed - return best attempt instead of original
    logger.error(f"  ❌ Layer 2: AI expansion failed after {max_attempts} attempts")
    logger.warning(f"     Returning BEST attempt: {best_words} words (divergence {best_divergence:.1f}%)")

    log_fallback(
        component="NARRATIVE_ARCHITECT_AI_EXPANSION",
        fallback_type="EXPANSION_FAILED",
        reason=f"AI expansion failed after {max_attempts} attempts. Best: {best_words} words ({best_divergence:.1f}% divergence)",
        impact="MEDIUM"
    )

    # Return best attempt (not original) to minimize divergence
    return best_narrative_arc
