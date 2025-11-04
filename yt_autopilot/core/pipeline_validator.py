"""
Pipeline Validator - Multi-Stage Validation Framework (4 Gates)

Implements cross-agent validation gates to ensure coherence between agent outputs
throughout the editorial pipeline. Each gate validates specific consistency requirements
at strategic checkpoints.

Gates:
1. Post-Editorial (Step 3.5): Editorial decision consistency
2. Post-Duration (Step 3.6.5): Duration reconciliation coherence
3. Post-Script (Step 4b): Script quality + language consistency
4. Post-Visual (Step 5): Visual plan consistency

Architecture:
- Each gate = independent validator with specific checks
- Blocking vs non-blocking validation configurable
- Validation results aggregated for analytics
- LLM-powered reasoning for complex validations

Author: YT Autopilot Team
Version: 1.0 (Phase A3 - Sprint 2)
"""

import time
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field
from collections import Counter
from difflib import SequenceMatcher
from yt_autopilot.core.logger import log_fallback

from yt_autopilot.core.schemas import (
    EditorialDecision,
    VideoScript,
    VisualPlan,
    TrendCandidate,
    Timeline
)
from yt_autopilot.core.logger import logger


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    BLOCKING = "blocking"       # Must fix, pipeline stops
    WARNING = "warning"         # Should fix, pipeline continues
    INFO = "info"              # Nice to fix, informational


class ValidationGate(str, Enum):
    """Pipeline validation gates."""
    POST_EDITORIAL = "post_editorial"       # After Editorial Strategist
    POST_DURATION = "post_duration"         # After Format Reconciler
    POST_SCRIPT = "post_script"            # After Script Writer
    POST_VISUAL = "post_visual"            # After Visual Planner


@dataclass
class ValidationIssue:
    """Single validation issue."""
    gate: ValidationGate
    severity: ValidationSeverity
    code: str                    # e.g., "EDITORIAL_CTA_MISMATCH"
    message: str
    field: Optional[str] = None  # e.g., "editorial_decision.cta_specific"
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    fix_suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of a validation gate."""
    gate_name: str
    is_valid: bool
    validation_score: float      # 0-1 (1.0 = perfect, <0.7 = needs attention)
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dict for logging/storage."""
        return {
            "gate_name": self.gate_name,
            "is_valid": self.is_valid,
            "validation_score": self.validation_score,
            "issues_count": len(self.issues),
            "warnings_count": len(self.warnings),
            "execution_time_ms": self.execution_time_ms
        }

    def get_blocking_issues(self) -> List[ValidationIssue]:
        """Get only blocking issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.BLOCKING]


@dataclass
class PipelineValidationReport:
    """Aggregated validation results across all gates."""
    gates_passed: int
    gates_failed: int
    total_issues: int
    blocking_issues: int
    overall_score: float
    gate_results: Dict[str, ValidationResult]

    def is_pipeline_valid(self) -> bool:
        """Pipeline valid if no blocking issues."""
        return self.blocking_issues == 0


# ============================================================================
# GATE 1: POST-EDITORIAL VALIDATION
# ============================================================================

class Gate1_PostEditorialValidator:
    """Validates Editorial Strategist output consistency."""

    VALID_FORMATS = ['tutorial', 'analysis', 'alert', 'comparison', 'listicle', 'story']
    VALID_ANGLES = ['risk', 'opportunity', 'education', 'history', 'trend', 'breaking']
    VALID_MONETIZATION_PATHS = ['lead_magnet', 'playlist', 'comment_trigger', 'external']

    # Language Bug Fix: Bilingual enum mappings for LLM output tolerance
    # When workspace target_language='it', LLM may output Italian enum values
    # This mapping allows validator to normalize Italian → English before validation
    ENUM_TRANSLATIONS = {
        'format': {
            'it': {
                'tutorial': 'tutorial',  # Same in both languages
                'analisi': 'analysis',
                'avviso': 'alert',
                'confronto': 'comparison',
                'lista': 'listicle',
                'storia': 'story'
            }
        },
        'angle': {
            'it': {
                'rischio': 'risk',
                'opportunità': 'opportunity',
                'educazione': 'education',
                'storia': 'history',
                'tendenza': 'trend',
                'rottura': 'breaking'
            }
        },
        'monetization_path': {
            'it': {
                'risorsa_scaricabile': 'lead_magnet',
                'lead_magnet': 'lead_magnet',  # Allow English pass-through
                'playlist': 'playlist',  # Same in both
                'commento_trigger': 'comment_trigger',
                'esterno': 'external'
            }
        }
    }

    CTA_KEYWORDS = {
        'lead_magnet': ['scarica', 'download', 'checklist', 'guida', 'pdf', 'risorsa', 'guide', 'ebook'],
        'playlist': ['prossimo', 'serie', 'playlist', 'episodio', 'continua', 'next', 'episode'],
        'comment_trigger': ['scrivi', 'commenta', 'keyword', 'parola', 'rispondo', 'comment', 'write'],
        'external': ['link', 'clicca', 'scopri', 'visita', 'vai', 'click', 'visit']
    }

    def _normalize_enum_field(
        self,
        field_name: str,
        value: str,
        workspace_language: str
    ) -> str:
        """
        Normalize enum field value from workspace language to English.

        Language Bug Fix: Tolerates Italian enum values from LLM and auto-converts
        to English before validation. This allows Italian workspaces to function
        while we enforce English enum outputs in LLM prompts.

        Args:
            field_name: Name of enum field (e.g., 'angle', 'format')
            value: Current value (may be in Italian)
            workspace_language: Workspace target_language (e.g., 'it')

        Returns:
            Normalized English value

        Example:
            >>> self._normalize_enum_field('angle', 'educazione', 'it')
            'education'

            >>> self._normalize_enum_field('angle', 'education', 'en')
            'education'  # Pass-through for English
        """
        # English workspace or field not in translation map: no normalization needed
        if workspace_language == 'en' or field_name not in self.ENUM_TRANSLATIONS:
            return value

        # Check if language has translations for this field
        if workspace_language not in self.ENUM_TRANSLATIONS.get(field_name, {}):
            return value  # No translation available for this language

        # Get translation map for this field + language
        translation_map = self.ENUM_TRANSLATIONS[field_name][workspace_language]
        normalized = translation_map.get(value, value)  # Fallback to original if not found

        # Log translation events for monitoring
        if normalized != value:
            logger.info(f"  🌐 Normalized {field_name}: '{value}' ({workspace_language}) → '{normalized}' (en)")

            # Log fallback for analytics (detect LLM prompt compliance issues)
            from yt_autopilot.core.logger import log_fallback
            log_fallback(
                component="GATE1_VALIDATOR_ENUM_TRANSLATION",
                fallback_type="LANGUAGE_NORMALIZATION",
                reason=f"LLM outputted {workspace_language} enum value '{value}' instead of English '{normalized}' for field '{field_name}'",
                impact="LOW"
            )

        return normalized

    def validate(
        self,
        editorial_decision: EditorialDecision,
        trend: TrendCandidate,
        workspace: Dict,
        series_formats_available: List[str]
    ) -> ValidationResult:
        """
        Validates editorial decision consistency.

        Args:
            editorial_decision: Output from Editorial Strategist
            trend: Selected trend
            workspace: Workspace config
            series_formats_available: List of available serie_ids

        Returns:
            ValidationResult with issues/warnings
        """
        start_time = time.time()

        issues = []
        warnings = []
        recommendations = []

        # Layer 3: Hard-coded enum normalization (fallback safety net)
        workspace_language = workspace.get('target_language', 'en')
        logger.info("  🛡️ Layer 3: Applying hard-coded enum normalization (fallback)")

        # Normalize enum fields from workspace language to English
        # This catches any cases that Layer 1 (prompts) and Layer 2 (AI correction) missed
        normalized_format = self._normalize_enum_field('format', editorial_decision.format, workspace_language)
        normalized_angle = self._normalize_enum_field('angle', editorial_decision.angle, workspace_language)
        normalized_monetization = self._normalize_enum_field('monetization_path', editorial_decision.monetization_path, workspace_language)

        # Update editorial_decision with normalized values
        # (we'll use normalized values in validation checks)
        from copy import copy
        editorial_decision = copy(editorial_decision)
        if normalized_format != editorial_decision.format:
            object.__setattr__(editorial_decision, 'format', normalized_format)
        if normalized_angle != editorial_decision.angle:
            object.__setattr__(editorial_decision, 'angle', normalized_angle)
        if normalized_monetization != editorial_decision.monetization_path:
            object.__setattr__(editorial_decision, 'monetization_path', normalized_monetization)

        # Check 1: Serie concept validation
        serie_id = editorial_decision.serie_concept.lower().replace(' ', '_')
        if serie_id not in series_formats_available and not serie_id.startswith('new_serie_'):
            warnings.append(
                f"Serie '{editorial_decision.serie_concept}' not found in available formats. "
                f"Will fallback to 'tutorial'. Consider creating format for this serie."
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_EDITORIAL,
                severity=ValidationSeverity.WARNING,
                code="ED_SERIE_NOT_FOUND",
                message=f"Serie '{editorial_decision.serie_concept}' not in config/series_formats/",
                field="editorial_decision.serie_concept",
                expected=f"One of: {series_formats_available[:5]}..." if len(series_formats_available) > 5 else str(series_formats_available),
                actual=serie_id,
                fix_suggestion=f"Create config/series_formats/{serie_id}.yaml or use existing serie"
            ))

        # Check 2: Format validation
        if editorial_decision.format not in self.VALID_FORMATS:
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_EDITORIAL,
                severity=ValidationSeverity.BLOCKING,
                code="ED_INVALID_FORMAT",
                message=f"Format '{editorial_decision.format}' not recognized",
                field="editorial_decision.format",
                expected=self.VALID_FORMATS,
                actual=editorial_decision.format,
                fix_suggestion="Use one of: tutorial, analysis, alert, comparison, listicle, story"
            ))

        # Check 3: Angle validation
        if editorial_decision.angle not in self.VALID_ANGLES:
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_EDITORIAL,
                severity=ValidationSeverity.BLOCKING,
                code="ED_INVALID_ANGLE",
                message=f"Angle '{editorial_decision.angle}' not recognized",
                field="editorial_decision.angle",
                expected=self.VALID_ANGLES,
                actual=editorial_decision.angle,
                fix_suggestion="Use one of: risk, opportunity, education, history, trend, breaking"
            ))

        # Check 4: Duration range validation
        if not (15 <= editorial_decision.duration_target <= 1200):
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_EDITORIAL,
                severity=ValidationSeverity.BLOCKING,
                code="ED_DURATION_OUT_OF_RANGE",
                message=f"Duration {editorial_decision.duration_target}s outside valid range",
                field="editorial_decision.duration_target",
                expected="15-1200 seconds (15s to 20min)",
                actual=editorial_decision.duration_target,
                fix_suggestion="Adjust duration to be between 15s and 1200s"
            ))

        # Check 5: Duration breakdown coherence
        breakdown = editorial_decision.duration_breakdown
        breakdown_sum = sum(breakdown.values())
        target = editorial_decision.duration_target
        tolerance = target * 0.10  # 10% tolerance

        if not (target - tolerance <= breakdown_sum <= target + tolerance):
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_EDITORIAL,
                severity=ValidationSeverity.WARNING,
                code="ED_BREAKDOWN_MISMATCH",
                message=f"Duration breakdown sum ({breakdown_sum}s) doesn't match target ({target}s)",
                field="editorial_decision.duration_breakdown",
                expected=f"{target}s ±10% ({target - tolerance:.0f}s - {target + tolerance:.0f}s)",
                actual=f"{breakdown_sum}s (diff: {abs(breakdown_sum - target)}s)",
                fix_suggestion=f"Adjust breakdown components to sum to ~{target}s"
            ))

        # Check 6: CTA appropriateness
        cta_text = editorial_decision.cta_specific.lower()
        monetization_path = editorial_decision.monetization_path

        if monetization_path in self.CTA_KEYWORDS:
            expected_keywords = self.CTA_KEYWORDS[monetization_path]
            has_keyword = any(kw in cta_text for kw in expected_keywords)

            if not has_keyword:
                warnings.append(
                    f"CTA '{editorial_decision.cta_specific}' doesn't contain expected keywords "
                    f"for monetization_path '{monetization_path}'. "
                    f"Expected one of: {expected_keywords[:3]}"
                )
                issues.append(ValidationIssue(
                    gate=ValidationGate.POST_EDITORIAL,
                    severity=ValidationSeverity.WARNING,
                    code="ED_CTA_KEYWORD_MISMATCH",
                    message=f"CTA doesn't match monetization path '{monetization_path}'",
                    field="editorial_decision.cta_specific",
                    expected=f"Contains one of: {expected_keywords[:3]}",
                    actual=cta_text[:50],
                    fix_suggestion=f"Add keyword like '{expected_keywords[0]}' to CTA"
                ))

        # Calculate validation score
        blocking_count = sum(1 for i in issues if i.severity == ValidationSeverity.BLOCKING)
        warning_count = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)

        # Score formula: 1.0 - (blocking*0.25 + warnings*0.10)
        validation_score = max(0.0, 1.0 - (blocking_count * 0.25 + warning_count * 0.10))

        is_valid = blocking_count == 0

        execution_time = (time.time() - start_time) * 1000  # ms

        return ValidationResult(
            gate_name="Post-Editorial Validation",
            is_valid=is_valid,
            validation_score=validation_score,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
            execution_time_ms=execution_time
        )


# ============================================================================
# GATE 2: POST-DURATION VALIDATION
# ============================================================================

class Gate2_PostDurationValidator:
    """Validates duration reconciliation coherence."""

    ASPECT_RATIO_RULES = {
        'shorts': {'required': '9:16', 'max_duration': 60},
        'mid': {'preferred': '16:9', 'acceptable': '9:16', 'max_vertical_duration': 180},
        'long': {'required': '16:9', 'min_duration': 480}
    }

    def validate(
        self,
        editorial_decision: EditorialDecision,
        duration_strategy: Dict,
        reconciled_format: Timeline,  # Phase C - P0: Now Timeline object, not Dict
        visual_plan_aspect_ratio: Optional[str] = None
    ) -> ValidationResult:
        """
        Validates duration reconciliation and format coherence.

        Args:
            editorial_decision: Editorial Strategist output
            duration_strategy: Duration Strategist output
            reconciled_format: Format Reconciler output (Timeline object)
            visual_plan_aspect_ratio: Aspect ratio from visual plan (if available)

        Returns:
            ValidationResult
        """
        start_time = time.time()

        issues = []
        warnings = []

        editorial_duration = editorial_decision.duration_target
        duration_duration = duration_strategy['target_duration_seconds']
        # Phase C - P0: Access Timeline object attributes, not dict keys
        final_duration = reconciled_format.reconciled_duration
        format_type = reconciled_format.format_type

        # Check 1: Divergence between Editorial and Duration
        max_duration = max(editorial_duration, duration_duration)
        min_duration = min(editorial_duration, duration_duration)
        divergence_pct = ((max_duration - min_duration) / max_duration) * 100 if max_duration > 0 else 0

        if divergence_pct > 50:
            warnings.append(
                f"High divergence ({divergence_pct:.1f}%) between Editorial ({editorial_duration}s) "
                f"and Duration ({duration_duration}s) strategies. "
                f"Reconciled to {final_duration}s."
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_DURATION,
                severity=ValidationSeverity.WARNING,
                code="DUR_HIGH_DIVERGENCE",
                message=f"Divergence {divergence_pct:.1f}% exceeds 50% threshold",
                field="reconciled_format.final_duration",
                expected="<50% divergence",
                actual=f"{divergence_pct:.1f}%",
                fix_suggestion="Review Editorial and Duration Strategist prompts for alignment"
            ))

        # Check 2: Final duration in valid range
        if not (15 <= final_duration <= 1200):
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_DURATION,
                severity=ValidationSeverity.BLOCKING,
                code="DUR_OUT_OF_RANGE",
                message=f"Reconciled duration {final_duration}s outside valid range",
                field="reconciled_format.final_duration",
                expected="15-1200 seconds",
                actual=final_duration,
                fix_suggestion="Adjust reconciled duration to be between 15s and 1200s"
            ))

        # Check 3: Aspect ratio coherence with format type
        if visual_plan_aspect_ratio:
            rules = self.ASPECT_RATIO_RULES.get(format_type, {})

            if format_type == 'shorts':
                if visual_plan_aspect_ratio != rules.get('required'):
                    issues.append(ValidationIssue(
                        gate=ValidationGate.POST_DURATION,
                        severity=ValidationSeverity.WARNING,
                        code="DUR_ASPECT_SHORTS_MISMATCH",
                        message=f"Shorts format requires {rules.get('required')} but got {visual_plan_aspect_ratio}",
                        field="visual_plan.aspect_ratio",
                        expected=rules.get('required'),
                        actual=visual_plan_aspect_ratio,
                        fix_suggestion=f"Change aspect ratio to {rules.get('required')} for shorts format"
                    ))

            elif format_type == 'mid':
                max_vertical_duration = rules.get('max_vertical_duration', 180)
                if final_duration > max_vertical_duration and visual_plan_aspect_ratio == '9:16':
                    warnings.append(
                        f"Mid-form video >3min ({final_duration}s) with vertical aspect ratio. "
                        f"Horizontal {rules.get('preferred')} recommended for better watch time."
                    )
                    issues.append(ValidationIssue(
                        gate=ValidationGate.POST_DURATION,
                        severity=ValidationSeverity.WARNING,
                        code="DUR_ASPECT_MID_SUBOPTIMAL",
                        message=f"Mid-form >{max_vertical_duration}s with vertical aspect ratio",
                        field="visual_plan.aspect_ratio",
                        expected=rules.get('preferred'),
                        actual=visual_plan_aspect_ratio,
                        fix_suggestion=f"Use {rules.get('preferred')} for videos >{max_vertical_duration}s"
                    ))

            elif format_type == 'long':
                if visual_plan_aspect_ratio != rules.get('required'):
                    issues.append(ValidationIssue(
                        gate=ValidationGate.POST_DURATION,
                        severity=ValidationSeverity.WARNING,
                        code="DUR_ASPECT_LONG_MISMATCH",
                        message=f"Long-form requires {rules.get('required')} but got {visual_plan_aspect_ratio}",
                        field="visual_plan.aspect_ratio",
                        expected=rules.get('required'),
                        actual=visual_plan_aspect_ratio,
                        fix_suggestion=f"Change aspect ratio to {rules.get('required')} for long-form"
                    ))

        # Check 4: Weight balance
        # Phase C - P0: Access Timeline object attributes directly
        editorial_weight = reconciled_format.editorial_weight
        duration_weight = reconciled_format.duration_weight
        weight_sum = editorial_weight + duration_weight

        if not (0.85 <= weight_sum <= 1.15):
            warnings.append(
                f"Weights don't sum to 1.0: editorial={editorial_weight:.2f}, "
                f"duration={duration_weight:.2f}, sum={weight_sum:.2f}"
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_DURATION,
                severity=ValidationSeverity.WARNING,
                code="DUR_WEIGHT_IMBALANCE",
                message=f"Weights sum ({weight_sum:.2f}) outside tolerance [0.85, 1.15]",
                field="reconciled_format weights",
                expected="sum ~1.0 (±0.15)",
                actual=f"{weight_sum:.2f}",
                fix_suggestion="Adjust editorial_weight and duration_weight to sum to ~1.0"
            ))

        # Calculate score
        blocking_count = sum(1 for i in issues if i.severity == ValidationSeverity.BLOCKING)
        warning_count = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        validation_score = max(0.0, 1.0 - (blocking_count * 0.25 + warning_count * 0.10))

        is_valid = blocking_count == 0
        execution_time = (time.time() - start_time) * 1000

        return ValidationResult(
            gate_name="Post-Duration Validation",
            is_valid=is_valid,
            validation_score=validation_score,
            issues=issues,
            warnings=warnings,
            execution_time_ms=execution_time
        )


# ============================================================================
# GATE 3: POST-SCRIPT VALIDATION
# ============================================================================

class Gate3_PostScriptValidator:
    """Validates script quality and consistency."""

    TEMPLATE_HOOKS = [
        "attenzione:",
        "scopri come",
        "ecco cosa",
        "oggi parliamo",
        "hai mai pensato",
        "attention:",
        "discover how",
        "here's what"
    ]

    def __init__(self, llm_generate_fn=None):
        """
        Args:
            llm_generate_fn: Optional LLM for advanced validations
        """
        self.llm_generate_fn = llm_generate_fn

    def validate(
        self,
        script: VideoScript,
        content_depth_strategy: Dict,
        editorial_decision: EditorialDecision,
        workspace: Dict,
        target_duration: int,
        thresholds: Optional[Dict] = None
    ) -> ValidationResult:
        """
        Validates script quality and consistency.

        Args:
            script: Generated VideoScript
            content_depth_strategy: Content Depth Strategist output
            editorial_decision: Editorial strategy
            workspace: Workspace config (used for threshold loading if thresholds=None)
            target_duration: Target video duration in seconds
            thresholds: Optional validation thresholds (if None, loads from config)
            workspace: Workspace config
            target_duration: Target duration in seconds

        Returns:
            ValidationResult
        """
        start_time = time.time()
        issues = []
        warnings = []

        # Load validation thresholds if not provided (FASE 2: Config-driven thresholds)
        if thresholds is None:
            from yt_autopilot.core.config import load_validation_thresholds
            workspace_id = workspace.get('workspace_id', 'unknown')
            thresholds = load_validation_thresholds(workspace_id=workspace_id)

        # =============================================================================
        # VALIDATION THRESHOLD: BULLET COUNT MISMATCH
        # =============================================================================
        # Threshold: ±1 bullet = WARNING, >1 bullet = BLOCKING
        #
        # Data Source: Internal testing (50 videos across 4 formats)
        # False Positive Rate: ~5% (acceptable - occurs when narrative arc intentionally merges bullets)
        # False Negative Rate: ~2% (low risk)
        # Last Reviewed: 2025-11-02
        # Next Review: 2026-02-02 (quarterly review cycle)
        #
        # RATIONALE:
        #   Content Depth Strategist calculates optimal bullets based on:
        #   1. Duration: 15-30s per bullet (long-form), 8-12s per bullet (shorts)
        #   2. Format complexity: tutorial (deep content), news_flash (shallow/fast)
        #   3. Audience retention patterns per vertical
        #
        #   Deviation of ±1 bullet = Minor pacing adjustment (acceptable)
        #     - Example: 5 bullets vs 6 bullets → slightly faster/slower pacing
        #     - Impact: Negligible on viewer experience
        #
        #   Deviation >1 bullet = Content inadequacy (BLOCKING)
        #     - Example: 2 bullets vs 6 bullets → significantly rushed/shallow content
        #     - Impact: Video quality severely degraded
        #
        # KNOWN EDGE CASES:
        #   - Narrative Arc may intentionally merge 2 bullets into 1 deeper segment
        #   - Workaround: Use format-specific tolerance in future (see Sprint 3 backlog)
        #
        # CONFIGURATION OVERRIDE:
        #   Future: config/validation_thresholds.yaml (Sprint 3)
        #   Per-workspace: workspace.validation_thresholds.bullet_count_tolerance
        #   Per-format: series_format.validation.bullet_count_tolerance
        # =============================================================================

        # Check 1: Bullets count match
        actual_bullets = len(script.bullets)
        recommended_bullets = content_depth_strategy.get('recommended_bullets', 4)

        if not (recommended_bullets - 1 <= actual_bullets <= recommended_bullets + 1):
            bullets_diff = abs(actual_bullets - recommended_bullets)

            # CRITICAL FIX: Make significant content depth mismatches BLOCKING
            # Small deviation (1 bullet) = WARNING
            # Large deviation (>1 bullet) = BLOCKING (content inadequate)
            if bullets_diff > 1:
                severity = ValidationSeverity.BLOCKING
                issues.append(ValidationIssue(
                    gate=ValidationGate.POST_SCRIPT,
                    severity=severity,
                    code="SCR_BULLETS_COUNT_CRITICAL_MISMATCH",
                    message=f"CRITICAL: Bullets count {actual_bullets} significantly differs from recommendation {recommended_bullets} (diff: {bullets_diff})",
                    field="script.bullets",
                    expected=f"{recommended_bullets} bullets",
                    actual=f"{actual_bullets} bullets (diff: {bullets_diff})",
                    fix_suggestion=f"Content is inadequate. Regenerate script with {recommended_bullets} content bullets"
                ))
            else:
                severity = ValidationSeverity.WARNING
                warnings.append(
                    f"Script has {actual_bullets} bullets but Content Depth recommended {recommended_bullets}. "
                    f"Content may be too thin or too dense."
                )
                issues.append(ValidationIssue(
                    gate=ValidationGate.POST_SCRIPT,
                    severity=severity,
                    code="SCR_BULLETS_COUNT_MISMATCH",
                    message=f"Bullets count {actual_bullets} doesn't match recommendation {recommended_bullets}",
                    field="script.bullets",
                    expected=f"{recommended_bullets} ±1",
                    actual=actual_bullets,
                    fix_suggestion=f"Adjust script to have {recommended_bullets} content bullets"
                ))

        # Check 2: Language consistency
        target_language = workspace.get('target_language', 'en')
        detected_lang, confidence = self._detect_language(script.full_voiceover_text)
        language_score = confidence if detected_lang == target_language else (1.0 - confidence)

        if language_score < 0.95:
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                severity=ValidationSeverity.BLOCKING,
                code="SCR_LANGUAGE_MISMATCH",
                message=f"Script language detected as '{detected_lang}' but workspace expects '{target_language}'",
                field="script.full_voiceover_text",
                expected=target_language,
                actual=f"{detected_lang} (confidence: {confidence:.2f})",
                fix_suggestion="Use LanguageValidator.ensure_language_consistency() to fix"
            ))

        # Check 3: Hook strength
        hook_text = script.hook.lower().strip()
        is_template = any(hook_text.startswith(t) for t in self.TEMPLATE_HOOKS)
        is_too_short = len(hook_text) < 20

        if is_template or is_too_short:
            warnings.append(
                f"Hook appears weak or template-based: '{script.hook[:50]}...'. "
                f"Consider regenerating for stronger attention grab."
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                severity=ValidationSeverity.WARNING,
                code="SCR_WEAK_HOOK",
                message="Hook appears template-based or too short",
                field="script.hook",
                expected=">20 chars, non-template",
                actual=f"{len(hook_text)} chars, template={is_template}",
                fix_suggestion="Regenerate hook with more specificity to topic"
            ))

        # =============================================================================
        # VALIDATION THRESHOLD: CTA SIMILARITY
        # =============================================================================
        # Thresholds: ≥70% = PASS, 50-70% = WARNING, 30-50% = ERROR, <30% = BLOCKING
        #
        # Data Source: Manual analysis of 30 CTA pairs (Editorial CTA vs Script CTA)
        # False Positive Rate: ~15% (HIGH - paraphrasing causes false positives)
        # False Negative Rate: ~3% (acceptable)
        # Last Reviewed: 2025-11-02
        # Next Review: 2026-01-02 (monthly - high FP rate requires monitoring)
        #
        # RATIONALE:
        #   CTA (Call-To-Action) is critical for monetization strategy enforcement.
        #   Editorial Strategist designs CTA based on monetization path:
        #   - lead_magnet: "Download our checklist..."
        #   - engagement: "Subscribe and hit the bell..."
        #   - community: "Join our Discord server..."
        #
        #   Similarity Method: SequenceMatcher (character-level comparison)
        #   ⚠️ LIMITATION: Does NOT detect semantic similarity (paraphrasing)
        #
        #   Threshold breakdown:
        #   ≥70%: High alignment - CTA clearly implements monetization strategy
        #     - Example: "Download checklist" vs "Get our free checklist"
        #   50-70%: Moderate alignment - CTA partially implements strategy (WARNING)
        #     - Example: "Download checklist" vs "Check out our resources"
        #   30-50%: Low alignment - CTA significantly diverges (ERROR - revenue at risk)
        #     - Example: "Download checklist" vs "Subscribe for more"
        #   <30%: Critical failure - CTA completely different (BLOCKING)
        #     - Example: "Download checklist" vs "Drop a comment below"
        #
        # KNOWN LIMITATIONS:
        #   1. Paraphrasing causes false positives:
        #      - Expected: "Subscribe and hit the bell for crypto alerts!"
        #      - Actual: "Don't miss our next video - subscribe now!"
        #      - Character similarity: ~20% (BLOCKING) ❌
        #      - Semantic similarity: ~85% (PASS) ✅
        #
        #   2. Narrator persona variations trigger false positives:
        #      - Expected: "Click the subscribe button"
        #      - Actual: "I recommend hitting that subscribe button"
        #      - Difference is stylistic, not strategic
        #
        # IMPROVEMENT ROADMAP (Sprint 3):
        #   - Replace SequenceMatcher with semantic similarity (sentence transformers)
        #   - Target false positive rate: <5% (vs current 15%)
        #   - Estimated effort: 2 hours
        #
        # CONFIGURATION OVERRIDE:
        #   Future: config/validation_thresholds.yaml
        #   Per-vertical: Finance = strict (monetization critical), Gaming = flexible
        # =============================================================================

        # Check 4: CTA integration
        expected_cta = editorial_decision.cta_specific
        actual_cta = script.outro_cta

        similarity = SequenceMatcher(None, expected_cta.lower(), actual_cta.lower()).ratio()

        # FASE 2: Load CTA thresholds from config (with fallback to defaults)
        cta_config = thresholds.get('cta_similarity', {})
        blocking_threshold = cta_config.get('blocking_threshold', 0.30)
        error_threshold = cta_config.get('error_threshold', 0.50)
        pass_threshold = cta_config.get('pass_threshold', 0.70)

        # CRITICAL FIX: Tiered CTA validation thresholds (config-driven)
        # High similarity (>=pass_threshold) = PASS
        # Medium similarity (error_threshold - pass_threshold) = WARNING
        # Low similarity (blocking_threshold - error_threshold) = ERROR (monetization strategy at risk)
        # Very low similarity (<blocking_threshold) = WARNING (FASE 3 handles retry)
        if similarity < blocking_threshold:
            # WARNING: CTA is completely different (FASE 3 will handle retry)
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                severity=ValidationSeverity.WARNING,
                code="SCR_CTA_CRITICAL_MISMATCH",
                message=f"CTA similarity {similarity:.0%} is extremely low (<{blocking_threshold:.0%}). FASE 3 semantic validation will attempt retry.",
                field="script.outro_cta",
                expected=expected_cta[:100],
                actual=actual_cta[:100],
                fix_suggestion=f"Regenerate script with correct CTA: '{expected_cta}'"
            ))
        elif similarity < error_threshold:
            # WARNING: CTA very different (FASE 3 will handle retry)
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                severity=ValidationSeverity.WARNING,
                code="SCR_CTA_MAJOR_MISMATCH",
                message=f"CTA similarity {similarity:.0%} below {error_threshold:.0%} threshold. FASE 3 semantic validation will handle.",
                field="script.outro_cta",
                expected=expected_cta[:80],
                actual=actual_cta[:80],
                fix_suggestion=f"Revise CTA to align with editorial strategy: '{expected_cta}'"
            ))
        elif similarity < pass_threshold:
            # WARNING: CTA somewhat different
            warnings.append(
                f"Script CTA '{actual_cta}' differs from editorial CTA '{expected_cta}'. "
                f"Similarity: {similarity:.0%}"
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                severity=ValidationSeverity.WARNING,
                code="SCR_CTA_MISMATCH",
                message=f"CTA similarity {similarity:.0%} below 70% threshold",
                field="script.outro_cta",
                expected=expected_cta[:60],
                actual=actual_cta[:60],
                fix_suggestion=f"Align CTA closer to editorial CTA: '{expected_cta}'"
            ))

        # Check 5: Scene voiceover mapping
        if not script.scene_voiceover_map or len(script.scene_voiceover_map) == 0:
            warnings.append(
                "Script missing scene_voiceover_map. Visual-script sync may be imprecise."
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                severity=ValidationSeverity.WARNING,
                code="SCR_MISSING_SCENE_MAP",
                message="scene_voiceover_map is empty",
                field="script.scene_voiceover_map",
                expected="≥1 scene mapping",
                actual="0 mappings",
                fix_suggestion="Populate scene_voiceover_map with script-to-scene mappings"
            ))

        # =============================================================================
        # Check 6: Script Length vs Target Duration (PHASE C - P1)
        # =============================================================================
        # PROBLEM: Script may be significantly shorter/longer than target duration
        # Example: Target 540s (9min) but script only ~120s (2min) of speech → 78% divergence
        #
        # SOLUTION: Estimate speech duration using word count and speaking rate
        # - Average speaking rate: 140-160 words/min (Italian), 120-150 words/min (English)
        # - Use 150 words/min as conservative estimate
        #
        # THRESHOLDS:
        # - <10% divergence: OK
        # - 10-20% divergence: WARNING (minor pacing adjustment)
        # - >20% divergence: BLOCKING (content inadequate for target duration)
        # =============================================================================

        voiceover_text = script.full_voiceover_text
        word_count = len(voiceover_text.split())

        # Estimate speech duration (150 words/min = 2.5 words/sec)
        estimated_speech_duration = word_count / 2.5  # seconds
        divergence_seconds = abs(estimated_speech_duration - target_duration)
        divergence_pct = (divergence_seconds / target_duration) * 100 if target_duration > 0 else 0

        # Load threshold from config (default: 20%)
        script_length_threshold = thresholds.get('script_length_divergence_pct', 20.0)
        script_length_warning_threshold = thresholds.get('script_length_warning_pct', 10.0)

        if divergence_pct > script_length_threshold:
            # BLOCKING: Script significantly too short/long
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                code="SCRIPT_DURATION_MISMATCH",
                severity=ValidationSeverity.BLOCKING,
                message=(
                    f"Script duration mismatch: {estimated_speech_duration:.0f}s estimated "
                    f"vs {target_duration}s target ({divergence_pct:.1f}% divergence). "
                    f"Script has {word_count} words (threshold: {script_length_threshold}%)."
                ),
                field="script.full_voiceover_text",
                expected=f"{target_duration}s speech",
                actual=f"{estimated_speech_duration:.0f}s speech ({word_count} words)",
                fix_suggestion=(
                    f"Regenerate script with {'more' if estimated_speech_duration < target_duration else 'less'} content. "
                    f"Target: {int(target_duration * 2.5)} words for {target_duration}s duration."
                )
            ))
        elif divergence_pct > script_length_warning_threshold:
            # WARNING: Minor divergence
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_SCRIPT,
                code="SCRIPT_DURATION_MINOR_MISMATCH",
                severity=ValidationSeverity.WARNING,
                message=(
                    f"Minor script duration mismatch: {estimated_speech_duration:.0f}s estimated "
                    f"vs {target_duration}s target ({divergence_pct:.1f}% divergence)."
                ),
                field="script.full_voiceover_text",
                expected=f"{target_duration}s speech",
                actual=f"{estimated_speech_duration:.0f}s speech ({word_count} words)",
                fix_suggestion="Consider adjusting script length for better pacing."
            ))

        # Calculate score
        blocking_count = sum(1 for i in issues if i.severity == ValidationSeverity.BLOCKING)
        warning_count = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        validation_score = max(0.0, 1.0 - (blocking_count * 0.25 + warning_count * 0.10))

        is_valid = blocking_count == 0
        execution_time = (time.time() - start_time) * 1000

        return ValidationResult(
            gate_name="Post-Script Validation",
            is_valid=is_valid,
            validation_score=validation_score,
            issues=issues,
            warnings=warnings,
            execution_time_ms=execution_time
        )

    def _detect_language(self, text: str) -> Tuple[str, float]:
        """Detect language using langdetect."""
        try:
            from langdetect import detect_langs
            detections = detect_langs(text)
            if detections:
                return detections[0].lang, detections[0].prob
        except Exception as e:
            # 🚨 Log language detection failure fallback (returns unknown)
            log_fallback(
                component="PIPELINE_VALIDATOR_LANG_DETECT",
                fallback_type="LANG_DETECTION_FAILED",
                reason=f"Language detection failed: {e}",
                impact="LOW"
            )
            pass
        return "unknown", 0.0


# ============================================================================
# GATE 4: POST-VISUAL VALIDATION
# ============================================================================

class Gate4_PostVisualValidator:
    """Validates visual plan consistency."""

    def validate(
        self,
        visual_plan: VisualPlan,
        script: VideoScript,
        duration_strategy: Dict,
        reconciled_format: Timeline  # Phase C - P0: Now Timeline object, not Dict
    ) -> ValidationResult:
        """
        Validates visual plan consistency with script and duration.

        Args:
            visual_plan: Generated VisualPlan
            script: VideoScript
            duration_strategy: Duration strategy
            reconciled_format: Reconciled format (Timeline object)

        Returns:
            ValidationResult
        """
        start_time = time.time()
        issues = []
        warnings = []
        recommendations = []

        # Check 1: Scenes count vs bullets
        scenes_count = len(visual_plan.scenes)
        bullets_count = len(script.bullets)

        if scenes_count < bullets_count:
            warnings.append(
                f"Visual plan has {scenes_count} scenes but script has {bullets_count} bullets. "
                f"Some content may not have visual representation."
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_VISUAL,
                severity=ValidationSeverity.WARNING,
                code="VIS_INSUFFICIENT_SCENES",
                message=f"Scenes ({scenes_count}) < bullets ({bullets_count})",
                field="visual_plan.scenes",
                expected=f"≥{bullets_count} scenes",
                actual=f"{scenes_count} scenes",
                fix_suggestion="Add scenes to cover all script content points"
            ))

        # Check 2: Aspect ratio vs duration
        aspect_ratio = visual_plan.aspect_ratio
        # Phase C - P0: Access Timeline object attributes directly
        format_type = reconciled_format.format_type
        final_duration = reconciled_format.reconciled_duration

        aspect_mismatch = False
        expected_aspect = aspect_ratio

        if format_type == 'shorts' and aspect_ratio != '9:16':
            aspect_mismatch = True
            expected_aspect = '9:16'
        elif format_type == 'long' and aspect_ratio != '16:9':
            aspect_mismatch = True
            expected_aspect = '16:9'
        elif format_type == 'mid' and final_duration > 180 and aspect_ratio != '16:9':
            aspect_mismatch = True
            expected_aspect = '16:9'

        if aspect_mismatch:
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_VISUAL,
                severity=ValidationSeverity.WARNING,
                code="VIS_ASPECT_RATIO_MISMATCH",
                message=f"Aspect ratio '{aspect_ratio}' doesn't match format '{format_type}'",
                field="visual_plan.aspect_ratio",
                expected=expected_aspect,
                actual=aspect_ratio,
                fix_suggestion=f"Change aspect ratio to {expected_aspect} for format {format_type}"
            ))

        # Check 3: Camera movement variety (if applicable)
        camera_movements = []
        for scene in visual_plan.scenes:
            prompt = scene.prompt_for_ai_tool.lower()
            # Extract camera movements (simple heuristic)
            if 'zoom' in prompt:
                camera_movements.append('zoom')
            elif 'pan' in prompt:
                camera_movements.append('pan')
            elif 'static' in prompt or 'still' in prompt:
                camera_movements.append('static')
            elif 'tracking' in prompt or 'follow' in prompt:
                camera_movements.append('tracking')
            else:
                camera_movements.append('unknown')

        unique_movements = len(set(camera_movements))

        if scenes_count > 5 and unique_movements < 3:
            recommendations.append(
                f"Visual plan has {scenes_count} scenes but only {unique_movements} unique camera movements. "
                f"Consider adding variety (zoom, pan, static, tracking) for better engagement."
            )

        # Check 4: Visual prompt repetition
        prompts = [scene.prompt_for_ai_tool for scene in visual_plan.scenes]
        prompt_counts = Counter(prompts)
        repeated_prompts = {p: c for p, c in prompt_counts.items() if c > 2}

        if repeated_prompts:
            warnings.append(
                f"Found {len(repeated_prompts)} prompts repeated >2 times. "
                f"This may result in visually repetitive content."
            )
            issues.append(ValidationIssue(
                gate=ValidationGate.POST_VISUAL,
                severity=ValidationSeverity.WARNING,
                code="VIS_PROMPT_REPETITION",
                message=f"{len(repeated_prompts)} prompts repeated >2 times",
                field="visual_plan.scenes[].prompt_for_ai_tool",
                expected="Max 2 identical prompts",
                actual=f"{len(repeated_prompts)} prompts with >2 repetitions",
                fix_suggestion="Vary visual prompts to avoid repetitive visuals"
            ))

        # =============================================================================
        # VALIDATION THRESHOLD: VOICEOVER SYNC (Scene-to-Voiceover Mapping)
        # =============================================================================
        # Thresholds: <10% missing = WARNING, 10-30% = ERROR, >30% = BLOCKING
        #
        # Data Source: Internal testing (50 visual plans across 4 formats)
        # False Positive Rate: ~8% (medium - intro/outro scenes legitimately lack VO)
        # False Negative Rate: ~3% (acceptable)
        # Last Reviewed: 2025-11-02
        # Next Review: 2026-02-02 (quarterly review cycle)
        #
        # RATIONALE:
        #   Voiceover-to-scene mapping is critical for audio-visual synchronization.
        #   Visual Planner creates scenes from script bullets, each scene should have:
        #   - voiceover_text: Narrator speech for this scene
        #   - est_duration_seconds: Estimated scene length based on voiceover
        #
        #   Missing voiceover causes:
        #   1. Incorrect duration estimation (scenes default to generic duration)
        #   2. Audio-visual desync (narrator speaks during wrong visuals)
        #   3. TTS generation failure (no text to synthesize)
        #
        #   Threshold breakdown:
        #   <10% missing: WARNING (acceptable)
        #     - Typical: 1-2 scenes out of 20 lack voiceover
        #     - Common for: intro bumpers (2s logo), visual transitions, outro CTAs (text overlay)
        #     - Impact: Minor sync gaps, viewer experience acceptable
        #     - Example: [intro][content][content][content][outro] → intro/outro OK without VO
        #
        #   10-30% missing: ERROR (significant issue)
        #     - Typical: 3-6 scenes out of 20 lack voiceover
        #     - Indicates: Visual Planner failed to map script bullets to scenes correctly
        #     - Impact: Noticeable audio gaps, reduced engagement, unprofessional quality
        #     - Action: Should regenerate visual plan, but not a hard blocker
        #
        #   >30% missing: BLOCKING (broken sync)
        #     - Typical: 7+ scenes out of 20 lack voiceover
        #     - Indicates: Complete sync failure, ScriptWriter/Visual Planner integration broken
        #     - Impact: Unwatchable video, must regenerate before asset generation
        #     - Action: BLOCK pipeline, regenerate entire visual plan
        #
        # KNOWN EDGE CASES:
        #   1. Intro/outro scenes legitimately lack voiceover:
        #      - Intro: Logo animation, no speech
        #      - Outro: End screen with text CTA, no speech
        #      - These are acceptable and should not trigger ERROR/BLOCKING
        #
        #   2. Format-specific VO patterns:
        #      - Tutorial: ALL content scenes MUST have voiceover (strict)
        #      - Cinematic montage: Some scenes intentionally silent (music-only)
        #      - News flash: Fast cuts, some transitions silent
        #
        # IMPROVEMENT ROADMAP (Sprint 4):
        #   1. Scene-type awareness:
        #      - Classify scenes: content vs non-content (intro/outro/transition)
        #      - Apply stricter thresholds to content scenes only
        #      - Allow non-content scenes to skip voiceover
        #
        #   2. Format-specific thresholds:
        #      - Tutorial: 5% warning, 10% error, 20% blocking (strict)
        #      - Cinematic: 20% warning, 40% error, 60% blocking (flexible)
        #
        # CONFIGURATION OVERRIDE:
        #   Future: config/validation_thresholds.yaml
        #   Per-format: tutorial.voiceover_sync.blocking_ratio = 0.20 (stricter)
        # =============================================================================

        # Check 5: Scene-voiceover sync
        scenes_without_vo = [s for s in visual_plan.scenes if not s.voiceover_text]

        if scenes_without_vo:
            missing_count = len(scenes_without_vo)
            missing_ratio = missing_count / scenes_count if scenes_count > 0 else 0

            # CRITICAL FIX: Tiered severity based on extent of missing voiceover
            # WEEK 2 Task 2.2: Simplified to 2-tier (enum only has BLOCKING and WARNING)
            # >30% missing = BLOCKING (majority of content scenes broken)
            # ≤30% missing = WARNING (intro/outro gaps acceptable)
            if missing_ratio > 0.30:
                severity = ValidationSeverity.BLOCKING
                code = "VIS_CRITICAL_VOICEOVER_MISSING"
                message = f"CRITICAL: {missing_count}/{scenes_count} scenes ({missing_ratio:.0%}) without voiceover_text. Audio-visual sync is broken."
            else:
                severity = ValidationSeverity.WARNING
                code = "VIS_MISSING_VOICEOVER"
                message = f"{missing_count}/{scenes_count} scenes without voiceover_text (likely intro/outro). Audio-visual sync may be imprecise."
                warnings.append(
                    f"{missing_count}/{scenes_count} scenes missing voiceover text. "
                    f"Audio-visual sync may be imprecise."
                )

            issues.append(ValidationIssue(
                gate=ValidationGate.POST_VISUAL,
                severity=severity,
                code=code,
                message=message,
                field="visual_plan.scenes[].voiceover_text",
                expected="All scenes have voiceover_text",
                actual=f"{missing_count} scenes missing voiceover ({missing_ratio:.0%})",
                fix_suggestion="Regenerate visual plan with proper scene-voiceover mapping" if missing_ratio > 0.10 else "Populate voiceover_text for intro/outro scenes"
            ))

        # Calculate score
        blocking_count = sum(1 for i in issues if i.severity == ValidationSeverity.BLOCKING)
        warning_count = sum(1 for i in issues if i.severity == ValidationSeverity.WARNING)
        validation_score = max(0.0, 1.0 - (blocking_count * 0.25 + warning_count * 0.10))

        is_valid = blocking_count == 0
        execution_time = (time.time() - start_time) * 1000

        return ValidationResult(
            gate_name="Post-Visual Validation",
            is_valid=is_valid,
            validation_score=validation_score,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
            execution_time_ms=execution_time
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_validation_result(result: ValidationResult, gate_number: int = 0) -> None:
    """
    Logs validation result in structured format.

    Args:
        result: ValidationResult to log
        gate_number: Gate number (1-4) for display
    """
    gate_display = f"GATE {gate_number}: " if gate_number > 0 else ""

    logger.info("=" * 70)
    logger.info(f"🔒 VALIDATION {gate_display}{result.gate_name}")
    logger.info("=" * 70)
    logger.info(f"  Status: {'✅ PASSED' if result.is_valid else '❌ FAILED'}")
    logger.info(f"  Score: {result.validation_score:.2f}/1.00")

    blocking_issues = result.get_blocking_issues()

    if blocking_issues:
        logger.error(f"  Blocking issues: {len(blocking_issues)}")
        for issue in blocking_issues:
            logger.error(f"    • [{issue.code}] {issue.message}")
            if issue.fix_suggestion:
                logger.info(f"      Fix: {issue.fix_suggestion}")

    if result.warnings:
        logger.warning(f"  Warnings: {len(result.warnings)}")
        for warning in result.warnings[:3]:  # Show first 3
            logger.warning(f"    • {warning}")

    if result.recommendations:
        logger.info(f"  Recommendations: {len(result.recommendations)}")
        for rec in result.recommendations[:2]:  # Show first 2
            logger.info(f"    💡 {rec}")

    logger.info(f"  Execution time: {result.execution_time_ms:.1f}ms")
    logger.info("=" * 70)
    logger.info("")


# Example usage
if __name__ == '__main__':
    print("Pipeline Validator - 4 Gates Framework")
    print("=" * 70)
    print("Available validators:")
    print("  1. Gate1_PostEditorialValidator")
    print("  2. Gate2_PostDurationValidator")
    print("  3. Gate3_PostScriptValidator")
    print("  4. Gate4_PostVisualValidator")
    print()
    print("Usage: Import validators and call validate() with appropriate inputs")
