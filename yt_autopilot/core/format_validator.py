"""
Format Validator - Aspect Ratio & Duration Coherence

Valida coerenza tra aspect ratio, duration, e workspace config.
Uno dei problemi critici trovati: workspace dice use_single_long_video=True
ma output produce 9:16 vertical (incompatibile).

Validation Rules:
- Shorts (<60s) → 9:16 vertical
- Mid-form (60-480s) → 16:9 horizontal (preferred for >3min)
- Long-form (>480s) → 16:9 horizontal (MUST)

Author: YT Autopilot Team
Version: 2.0 (AI-Driven Format Validation)
"""

from typing import Dict, Tuple, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Import truncation utilities for consistent log formatting
from yt_autopilot.core.logger import truncate_for_log
from yt_autopilot.core.config import LOG_TRUNCATE_REASONING


class FormatTier(str, Enum):
    """Format tiers basati su duration."""
    SHORTS = "shorts"       # <60s
    MID_FORM = "mid"        # 60-480s (1-8min)
    LONG_FORM = "long"      # >480s (8+min)


class AspectRatio(str, Enum):
    """Supported aspect ratios."""
    VERTICAL = "9:16"      # YouTube Shorts, TikTok, Reels
    HORIZONTAL = "16:9"    # Traditional YouTube, TV
    SQUARE = "1:1"         # Instagram (less common)


class FormatValidator:
    """
    Valida coerenza formato video (aspect ratio, duration, style).

    Usage:
        validator = FormatValidator()
        is_valid, issues, corrections = validator.validate_format_coherence(
            workspace_config=workspace,
            target_duration=480,
            aspect_ratio="9:16"
        )
    """

    # Aspect ratio rules per format tier
    ASPECT_RATIO_RULES = {
        FormatTier.SHORTS: {
            'aspect_ratio': AspectRatio.VERTICAL,
            'max_duration': 60,
            'optimal_duration': 30,
            'rationale': 'YouTube Shorts require vertical 9:16 format'
        },
        FormatTier.MID_FORM: {
            'aspect_ratio': AspectRatio.HORIZONTAL,  # Preferred
            'duration_range': (60, 480),
            'vertical_acceptable_until': 180,  # 3min threshold
            'rationale': 'Mid-form content performs better in horizontal 16:9 for watch time'
        },
        FormatTier.LONG_FORM: {
            'aspect_ratio': AspectRatio.HORIZONTAL,  # MUST
            'min_duration': 480,
            'rationale': 'Long-form content (8+min) MUST be horizontal 16:9 for mid-roll ads and desktop viewing'
        }
    }

    def __init__(self, llm_generate_fn: Optional[callable] = None):
        """
        Args:
            llm_generate_fn: Optional LLM function per AI-driven explanations
        """
        self.llm_generate_fn = llm_generate_fn

    def detect_format_tier(self, target_duration: int) -> FormatTier:
        """
        Detect format tier basato su duration.

        Args:
            target_duration: Duration in seconds

        Returns:
            FormatTier (shorts/mid/long)
        """
        if target_duration <= 60:
            return FormatTier.SHORTS
        elif target_duration <= 480:
            return FormatTier.MID_FORM
        else:
            return FormatTier.LONG_FORM

    def validate_format_coherence(
        self,
        workspace_config: Dict,
        target_duration: int,
        aspect_ratio: str,
        video_style_mode: Optional[Dict] = None
    ) -> Tuple[bool, List[str], Optional[Dict]]:
        """
        Valida coerenza formato.

        Args:
            workspace_config: Workspace config
            target_duration: Target duration in seconds
            aspect_ratio: Current aspect ratio (e.g., "9:16", "16:9")
            video_style_mode: Video style mode dict (if available)

        Returns:
            Tuple[is_valid, issues, corrections]
                - is_valid: True se formato è coerente
                - issues: Lista issue trovati
                - corrections: Dict con correzioni suggerite (None se valid)
        """
        logger.info("=" * 70)
        logger.info("FORMAT VALIDATION: Aspect Ratio & Duration Coherence")
        logger.info("=" * 70)

        issues = []
        corrections = {}

        # Detect format tier
        format_tier = self.detect_format_tier(target_duration)
        rules = self.ASPECT_RATIO_RULES[format_tier]

        logger.info(f"  Duration: {target_duration}s ({target_duration/60:.1f}min)")
        logger.info(f"  Format tier: {format_tier}")
        logger.info(f"  Aspect ratio: {aspect_ratio}")

        # Check 1: Aspect ratio matches format tier
        expected_aspect = rules['aspect_ratio']

        if format_tier == FormatTier.MID_FORM:
            # Mid-form has flexible rules
            if target_duration <= 180:  # ≤3min
                # Vertical acceptable
                if aspect_ratio not in [AspectRatio.VERTICAL, AspectRatio.HORIZONTAL]:
                    issues.append(
                        f"Aspect ratio '{aspect_ratio}' invalid. "
                        f"Mid-form ≤3min accepts both 9:16 (vertical) and 16:9 (horizontal)."
                    )
                    corrections['aspect_ratio'] = AspectRatio.HORIZONTAL
            else:  # >3min
                # Horizontal preferred
                if aspect_ratio != AspectRatio.HORIZONTAL:
                    issues.append(
                        f"Aspect ratio '{aspect_ratio}' not optimal for mid-form >3min. "
                        f"Expected: {AspectRatio.HORIZONTAL} (horizontal for better watch time)."
                    )
                    corrections['aspect_ratio'] = AspectRatio.HORIZONTAL
        else:
            # Shorts or Long-form have strict rules
            if aspect_ratio != expected_aspect:
                issues.append(
                    f"Aspect ratio '{aspect_ratio}' incompatible with {format_tier}. "
                    f"Expected: {expected_aspect}. Rationale: {rules['rationale']}"
                )
                corrections['aspect_ratio'] = expected_aspect

        # Check 2: Duration in valid range
        if 'max_duration' in rules and target_duration > rules['max_duration']:
            issues.append(
                f"Duration {target_duration}s exceeds {format_tier} max ({rules['max_duration']}s). "
                f"Should be reclassified as {FormatTier.MID_FORM}."
            )
            corrections['format_tier'] = FormatTier.MID_FORM
            corrections['aspect_ratio'] = AspectRatio.HORIZONTAL

        if 'min_duration' in rules and target_duration < rules['min_duration']:
            issues.append(
                f"Duration {target_duration}s below {format_tier} min ({rules['min_duration']}s). "
                f"Should be reclassified as {FormatTier.MID_FORM}."
            )
            corrections['format_tier'] = FormatTier.MID_FORM

        # Check 3: Workspace config hints compatibility
        if video_style_mode:
            # Check legacy use_single_long_video (now in _migration_hints)
            use_long_video = video_style_mode.get('use_single_long_video', False)
            if use_long_video:
                logger.warning("  ⚠️ DEPRECATED: use_single_long_video found in config (should be AI-driven)")
                if target_duration < 480:
                    issues.append(
                        f"Config indicates use_single_long_video=True but duration {target_duration}s < 480s. "
                        f"Long-form videos require ≥8min duration."
                    )
                    corrections['duration'] = 480  # Force to long-form min

                if aspect_ratio != AspectRatio.HORIZONTAL:
                    issues.append(
                        f"Config indicates use_single_long_video=True but aspect_ratio '{aspect_ratio}' is not horizontal. "
                        f"Long-form requires 16:9 horizontal."
                    )
                    corrections['aspect_ratio'] = AspectRatio.HORIZONTAL

        # Check migration hints (AI-friendly)
        migration_hints = workspace_config.get('_migration_hints', {})
        if migration_hints:
            video_style_pref = migration_hints.get('video_style_preference', {})
            legacy_long = video_style_pref.get('legacy_use_single_long', False)

            if legacy_long:
                logger.info(f"  📝 Migration hint: legacy preference for long-form video")
                # This is just a hint, not a hard constraint
                # AI can override, but we log inconsistency
                if format_tier != FormatTier.LONG_FORM:
                    logger.info(f"     Note: AI chose {format_tier} instead of long-form (AI override)")

        # Summary
        if issues:
            logger.error("=" * 70)
            logger.error(f"❌ FORMAT VALIDATION FAILED: {len(issues)} issues")
            logger.error("=" * 70)
            for issue in issues:
                logger.error(f"  • {issue}")

            if corrections:
                logger.info("")
                logger.info("💡 SUGGESTED CORRECTIONS:")
                for key, value in corrections.items():
                    logger.info(f"  • {key}: {value}")

            return False, issues, corrections
        else:
            logger.info("=" * 70)
            logger.info("✅ FORMAT VALIDATION PASSED")
            logger.info("=" * 70)
            return True, [], None

    def auto_correct_format(
        self,
        workspace_config: Dict,
        target_duration: int,
        aspect_ratio: str,
        video_style_mode: Optional[Dict] = None
    ) -> Tuple[int, str, str]:
        """
        Auto-corregge formato con LLM reasoning.

        Args:
            workspace_config: Workspace config
            target_duration: Current target duration
            aspect_ratio: Current aspect ratio
            video_style_mode: Video style mode dict

        Returns:
            Tuple[corrected_duration, corrected_aspect_ratio, reasoning]
        """
        is_valid, issues, corrections = self.validate_format_coherence(
            workspace_config,
            target_duration,
            aspect_ratio,
            video_style_mode
        )

        if is_valid:
            # No correction needed
            return target_duration, aspect_ratio, "Format already valid"

        # Apply corrections
        corrected_duration = corrections.get('duration', target_duration)
        corrected_aspect = corrections.get('aspect_ratio', aspect_ratio)

        # Generate LLM reasoning (if available)
        if self.llm_generate_fn:
            reasoning = self._generate_llm_correction_reasoning(
                workspace_config,
                target_duration,
                aspect_ratio,
                corrected_duration,
                corrected_aspect,
                issues
            )
        else:
            # Fallback deterministic reasoning
            reasoning = (
                f"Auto-corrected format: "
                f"duration {target_duration}s → {corrected_duration}s, "
                f"aspect_ratio '{aspect_ratio}' → '{corrected_aspect}'. "
                f"Reasons: {'; '.join(issues[:2])}"
            )

        logger.info("")
        logger.info("🔧 AUTO-CORRECTION APPLIED:")
        logger.info(f"  Duration: {target_duration}s → {corrected_duration}s")
        logger.info(f"  Aspect ratio: '{aspect_ratio}' → '{corrected_aspect}'")
        logger.info(f"  Reasoning: {truncate_for_log(reasoning, LOG_TRUNCATE_REASONING)}")

        return corrected_duration, corrected_aspect, reasoning

    def _generate_llm_correction_reasoning(
        self,
        workspace_config: Dict,
        original_duration: int,
        original_aspect: str,
        corrected_duration: int,
        corrected_aspect: str,
        issues: List[str]
    ) -> str:
        """
        Genera LLM reasoning per format correction.

        Args:
            workspace_config: Workspace config
            original_duration: Original duration
            original_aspect: Original aspect ratio
            corrected_duration: Corrected duration
            corrected_aspect: Corrected aspect ratio
            issues: Lista issues detected

        Returns:
            LLM-generated reasoning (1-2 sentences)
        """
        prompt = f"""
You are a YouTube video format expert explaining a format correction.

ORIGINAL FORMAT:
- Duration: {original_duration}s ({original_duration/60:.1f}min)
- Aspect ratio: {original_aspect}

CORRECTED FORMAT:
- Duration: {corrected_duration}s ({corrected_duration/60:.1f}min)
- Aspect ratio: {corrected_aspect}

ISSUES DETECTED:
{chr(10).join(f"- {issue}" for issue in issues[:3])}

TASK: Explain in 1-2 sentences WHY this correction was necessary.
Focus on YouTube algorithm and monetization implications.

EXPLANATION:
"""

        try:
            reasoning = self.llm_generate_fn(
                role="format_validator",
                task=prompt,
                context="",
                style_hints={"temperature": 0.3}
            )
            return reasoning.strip()

        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            return f"Format corrected to ensure YouTube compatibility and monetization potential."


def validate_and_enforce_format(
    workspace_config: Dict,
    target_duration: int,
    aspect_ratio: str,
    video_style_mode: Optional[Dict] = None,
    auto_correct: bool = True,
    llm_generate_fn: Optional[callable] = None
) -> Tuple[int, str, bool, Optional[str]]:
    """
    Convenience function per validate + auto-correct formato.

    Args:
        workspace_config: Workspace config
        target_duration: Target duration
        aspect_ratio: Aspect ratio
        video_style_mode: Video style mode
        auto_correct: Se True, applica auto-correction se validation fails
        llm_generate_fn: Optional LLM function

    Returns:
        Tuple[final_duration, final_aspect_ratio, was_corrected, reasoning]
    """
    validator = FormatValidator(llm_generate_fn)

    is_valid, issues, corrections = validator.validate_format_coherence(
        workspace_config,
        target_duration,
        aspect_ratio,
        video_style_mode
    )

    if is_valid:
        return target_duration, aspect_ratio, False, None

    if not auto_correct:
        logger.warning("⚠️ Format validation failed but auto_correct=False, returning original values")
        return target_duration, aspect_ratio, False, None

    # Auto-correct
    corrected_duration, corrected_aspect, reasoning = validator.auto_correct_format(
        workspace_config,
        target_duration,
        aspect_ratio,
        video_style_mode
    )

    return corrected_duration, corrected_aspect, True, reasoning


# Example usage
if __name__ == '__main__':
    # Mock workspace config
    workspace = {
        "workspace_id": "tech_ai_creator",
        "vertical_id": "tech_ai",
        "_migration_hints": {
            "video_style_preference": {
                "legacy_use_single_long": True
            }
        }
    }

    print("\n" + "=" * 70)
    print("DEMO: Format Validator")
    print("=" * 70)

    validator = FormatValidator()

    # Test 1: Valid shorts format
    print("\n1. VALID SHORTS FORMAT")
    is_valid, issues, corrections = validator.validate_format_coherence(
        workspace,
        target_duration=45,
        aspect_ratio="9:16"
    )
    print(f"   Result: {'PASS' if is_valid else 'FAIL'}")

    # Test 2: Invalid - long duration with vertical
    print("\n2. INVALID - Long duration with vertical aspect ratio")
    is_valid, issues, corrections = validator.validate_format_coherence(
        workspace,
        target_duration=600,  # 10min
        aspect_ratio="9:16"   # Vertical (wrong for long-form!)
    )
    print(f"   Result: {'PASS' if is_valid else 'FAIL'}")
    if corrections:
        print(f"   Suggested corrections: {corrections}")

    # Test 3: Auto-correction
    print("\n3. AUTO-CORRECTION")
    final_dur, final_aspect, was_corrected, reasoning = validate_and_enforce_format(
        workspace,
        target_duration=600,
        aspect_ratio="9:16",
        auto_correct=True
    )
    print(f"   Original: 600s, 9:16")
    print(f"   Corrected: {final_dur}s, {final_aspect}")
    print(f"   Was corrected: {was_corrected}")
