"""
Language Validator - Post-LLM Language Consistency Enforcement

Valida e corregge output LLM per garantire consistenza linguistica.
Uno dei problemi critici trovati: workspace configurato per italiano ma script generato in inglese.

Approach:
1. Post-LLM detection con langdetect
2. Se mismatch → LLM-driven translation + cultural adaptation (not literal)
3. Retry logic con max 2 attempts
4. Language consistency score (0-1)

Author: YT Autopilot Team
Version: 2.0 (AI-Driven Language Enforcement)
"""

from typing import Dict, Tuple, Optional, Callable
import logging
from enum import Enum
from yt_autopilot.core.logger import log_fallback

logger = logging.getLogger(__name__)


class LanguageCode(str, Enum):
    """Supported languages."""
    ITALIAN = "it"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    PORTUGUESE = "pt"


# Language names mapping (for prompts)
LANGUAGE_NAMES = {
    "it": "Italian (Italiano)",
    "en": "English",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "pt": "Portuguese (Português)"
}


class LanguageValidator:
    """
    Valida e corregge output LLM per language consistency.

    Usage:
        validator = LanguageValidator(target_language="it")
        validated_text = validator.ensure_language_consistency(
            llm_output="Hello world",
            llm_generate_fn=llm_router.generate_text
        )
        # Returns: "Ciao mondo" (LLM-translated)
    """

    def __init__(
        self,
        target_language: str = "en",
        strict_mode: bool = True,
        max_retries: int = 2
    ):
        """
        Args:
            target_language: Target language code (e.g., "it", "en")
            strict_mode: Se True, reject anche piccole deviations (emoji, code snippets in English)
            max_retries: Max tentativi di correzione (default: 2)
        """
        self.target_language = target_language
        self.strict_mode = strict_mode
        self.max_retries = max_retries

        # Validate target language
        if target_language not in LANGUAGE_NAMES:
            logger.warning(f"Unknown target language '{target_language}', defaulting to 'en'")
            self.target_language = "en"

    def detect_language(self, text: str) -> Tuple[str, float]:
        """
        Detect language usando langdetect.

        Args:
            text: Text da analizzare

        Returns:
            Tuple[language_code, confidence]
                - language_code: Detected language (e.g., "it", "en")
                - confidence: Confidence score 0-1 (langdetect è probabilistic)
        """
        try:
            import langdetect
            from langdetect import detect_langs

            # detect_langs returns list of (Language, probability) tuples
            detections = detect_langs(text)

            if detections:
                detected = detections[0]
                return detected.lang, detected.prob
            else:
                logger.warning("langdetect returned empty list, defaulting to 'en'")
                return "en", 0.5

        except ImportError as e:
            # 🚨 Log langdetect import failure fallback (assumes target language)
            log_fallback(
                component="LANGUAGE_VALIDATOR_DETECT",
                fallback_type="LANGDETECT_NOT_INSTALLED",
                reason=f"langdetect not installed: {e}",
                impact="MEDIUM"
            )
            logger.error("langdetect not installed! Install with: pip install langdetect")
            logger.warning("Skipping language detection (assuming target language)")
            return self.target_language, 1.0  # Assume target language

        except Exception as e:
            # 🚨 Log language detection failure fallback (returns unknown)
            log_fallback(
                component="LANGUAGE_VALIDATOR_DETECT",
                fallback_type="DETECTION_FAILED",
                reason=f"Language detection failed: {e}",
                impact="MEDIUM"
            )
            logger.error(f"Language detection failed: {e}")
            return "unknown", 0.0

    def calculate_language_consistency_score(
        self,
        text: str,
        target_language: str
    ) -> float:
        """
        Calcola language consistency score (0-1).

        Args:
            text: Text da validare
            target_language: Expected language

        Returns:
            Score 0-1:
                1.0 = Perfect match
                0.8-0.99 = Mostly correct (small deviations)
                0.5-0.79 = Mixed languages
                0.0-0.49 = Wrong language
        """
        detected_lang, confidence = self.detect_language(text)

        if detected_lang == target_language:
            # Perfect match
            return confidence  # Usually 0.95-0.99

        elif detected_lang == "unknown":
            # Detection failed, assume mixed
            return 0.6

        else:
            # Wrong language detected
            # Score inversely proportional to confidence in wrong language
            return max(0.0, 1.0 - confidence)

    def ensure_language_consistency(
        self,
        llm_output: str,
        llm_generate_fn: Callable,
        context: Optional[str] = None,
        component_name: str = "unknown"
    ) -> str:
        """
        Valida language consistency e corregge se necessario.

        Args:
            llm_output: Output LLM da validare
            llm_generate_fn: Function per chiamare LLM per translation/correction
                             Signature: fn(role: str, task: str, context: str) -> str
            context: Optional context per LLM correction
            component_name: Nome componente per logging (e.g., "script_hook", "seo_title")

        Returns:
            Validated/corrected text nella target language
        """
        logger.info(f"=" * 70)
        logger.info(f"LANGUAGE VALIDATION: {component_name}")
        logger.info(f"Target language: {LANGUAGE_NAMES[self.target_language]}")
        logger.info(f"=" * 70)

        # Detect language
        detected_lang, confidence = self.detect_language(llm_output)
        score = self.calculate_language_consistency_score(llm_output, self.target_language)

        logger.info(f"  Detected: {detected_lang} (confidence: {confidence:.2f})")
        logger.info(f"  Consistency score: {score:.2f}")

        # Check if validation passed
        if score >= 0.95:
            logger.info(f"  ✅ Language consistency PASSED (score {score:.2f})")
            return llm_output

        elif score >= 0.80 and not self.strict_mode:
            logger.warning(f"  ⚠️ Minor language deviations (score {score:.2f}), but passing (strict_mode=False)")
            return llm_output

        else:
            # Language mismatch detected
            logger.warning(f"  ❌ Language consistency FAILED (score {score:.2f})")
            logger.warning(f"     Expected: {self.target_language}, Detected: {detected_lang}")

            # Attempt LLM-driven correction
            corrected_output = self._attempt_language_correction(
                llm_output,
                llm_generate_fn,
                context,
                component_name,
                detected_lang
            )

            return corrected_output

    def _attempt_language_correction(
        self,
        wrong_output: str,
        llm_generate_fn: Callable,
        context: Optional[str],
        component_name: str,
        detected_lang: str,
        attempt: int = 1
    ) -> str:
        """
        Tenta correzione LLM-driven del language mismatch.

        Args:
            wrong_output: Output con wrong language
            llm_generate_fn: LLM function
            context: Optional context
            component_name: Component name per logging
            detected_lang: Detected language (wrong one)
            attempt: Current attempt number (for retry logic)

        Returns:
            Corrected output (hopefully in target language)
        """
        if attempt > self.max_retries:
            logger.error(f"  ❌ Max retries ({self.max_retries}) exceeded, returning original output")
            logger.error(f"     Language mismatch could not be fixed!")
            return wrong_output

        logger.info(f"  🔄 Attempting LLM-driven language correction (attempt {attempt}/{self.max_retries})...")

        target_lang_name = LANGUAGE_NAMES[self.target_language]
        detected_lang_name = LANGUAGE_NAMES.get(detected_lang, detected_lang)

        # Build correction prompt (LLM-driven translation + adaptation)
        correction_prompt = f"""
You are a professional translator and cultural adaptation specialist.

CRITICAL TASK: Translate and adapt the following content to {target_lang_name}.

DETECTED ISSUE:
- Current language: {detected_lang_name}
- Required language: {target_lang_name}

CONTENT TO TRANSLATE:
{wrong_output}

{f"CONTEXT: {context}" if context else ""}

TRANSLATION GUIDELINES:
1. ✅ Translate EVERYTHING to {target_lang_name} (no mixed languages)
2. ✅ Maintain tone and style (energetic → energico, professional → professionale)
3. ✅ Adapt culturally (not literal translation):
   - Idioms should be adapted to {target_lang_name} equivalents
   - Formatting should match {target_lang_name} conventions
   - Examples should be culturally relevant
4. ✅ Preserve markdown formatting if present
5. ✅ Preserve technical terms if universally known (API, CPU, etc.)
6. ❌ DO NOT add explanations or comments in English

OUTPUT REQUIREMENTS:
- MUST be 100% in {target_lang_name}
- MUST preserve original meaning and intent
- MUST match original length (±20%)
- NO preamble, NO "Here's the translation:", just the translated content

TRANSLATED CONTENT:
"""

        try:
            # Call LLM for correction
            corrected = llm_generate_fn(
                role="language_corrector",
                task=correction_prompt,
                context=context or "",
                style_hints={"temperature": 0.2}  # Low temp for consistency
            )

            # Validate correction
            corrected_score = self.calculate_language_consistency_score(
                corrected,
                self.target_language
            )

            logger.info(f"  ✓ LLM correction completed (new score: {corrected_score:.2f})")

            if corrected_score >= 0.95:
                logger.info(f"  ✅ Language correction SUCCESSFUL (score {corrected_score:.2f})")
                return corrected

            elif corrected_score > 0.80:
                logger.warning(f"  ⚠️ Correction improved score to {corrected_score:.2f} (acceptable)")
                return corrected

            else:
                # Still wrong, retry
                logger.warning(f"  ⚠️ Correction insufficient (score {corrected_score:.2f}), retrying...")
                return self._attempt_language_correction(
                    corrected,  # Use corrected as new input (iterative improvement)
                    llm_generate_fn,
                    context,
                    component_name,
                    detected_lang,
                    attempt=attempt + 1
                )

        except Exception as e:
            logger.error(f"  ❌ LLM correction failed: {e}")
            if attempt < self.max_retries:
                logger.info(f"  Retrying... (attempt {attempt + 1}/{self.max_retries})")
                return self._attempt_language_correction(
                    wrong_output,
                    llm_generate_fn,
                    context,
                    component_name,
                    detected_lang,
                    attempt=attempt + 1
                )
            else:
                # 🚨 Log language correction failure fallback (returns original output)
                log_fallback(
                    component="LANGUAGE_VALIDATOR_CORRECTION",
                    fallback_type="LLM_CORRECTION_FAILED",
                    reason=f"LLM correction failed after {self.max_retries} retries: {e}",
                    impact="HIGH"
                )
                logger.error("  Returning original output (correction failed)")
                return wrong_output

    def build_language_aware_prompt(
        self,
        base_prompt: str,
        target_language: str,
        include_examples: bool = True
    ) -> str:
        """
        Enhance prompt con language directives e few-shot examples.

        Args:
            base_prompt: Original prompt
            target_language: Target language code
            include_examples: Se True, include few-shot examples

        Returns:
            Enhanced prompt con language enforcement
        """
        target_lang_name = LANGUAGE_NAMES[target_language]

        # Language directive header
        language_header = f"""
⚠️ CRITICAL LANGUAGE REQUIREMENT ⚠️
══════════════════════════════════════════════════════════════════════
ALL OUTPUT MUST BE IN {target_lang_name.upper()}
DO NOT MIX LANGUAGES. DO NOT OUTPUT IN ENGLISH IF TARGET IS NOT ENGLISH.
══════════════════════════════════════════════════════════════════════

Target language: {target_lang_name}
Output language: {target_lang_name}
Required language: {target_lang_name}

"""

        # Few-shot examples (optional)
        examples = ""
        if include_examples:
            examples = self._get_few_shot_examples(target_language)

        # Combined prompt
        enhanced_prompt = language_header + examples + "\n" + base_prompt

        return enhanced_prompt

    def _get_few_shot_examples(self, target_language: str) -> str:
        """Get few-shot examples nella target language."""

        examples_by_language = {
            "it": """
EXAMPLES OF CORRECT OUTPUT IN ITALIAN:

Example 1 (Hook):
  ❌ WRONG: "Did you know that 70% of traders lose money?"
  ✅ CORRECT: "Lo sapevi che il 70% dei trader perde denaro?"

Example 2 (CTA):
  ❌ WRONG: "Subscribe for more content like this!"
  ✅ CORRECT: "Iscriviti per altri contenuti come questo!"

Example 3 (Content):
  ❌ WRONG: "Here are 3 tips to improve your workflow"
  ✅ CORRECT: "Ecco 3 consigli per migliorare il tuo flusso di lavoro"

""",
            "en": """
EXAMPLES OF CORRECT OUTPUT IN ENGLISH:

Example 1 (Hook):
  ✅ CORRECT: "Did you know that 70% of traders lose money?"

Example 2 (CTA):
  ✅ CORRECT: "Subscribe for more content like this!"

Example 3 (Content):
  ✅ CORRECT: "Here are 3 tips to improve your workflow"

"""
        }

        return examples_by_language.get(target_language, "")


def wrap_llm_with_language_enforcement(
    llm_generate_fn: Callable,
    target_language: str,
    strict_mode: bool = True,
    component_name: str = "unknown"
) -> Callable:
    """
    Wrapper function per enforce language consistency su ogni LLM call.

    Args:
        llm_generate_fn: Original LLM function
        target_language: Target language code
        strict_mode: Strict validation mode
        component_name: Component name per logging

    Returns:
        Wrapped function che automatically validates language

    Usage:
        enforced_llm = wrap_llm_with_language_enforcement(
            llm_router.generate_text,
            target_language="it"
        )

        # Use enforced_llm instead of direct llm call
        output = enforced_llm(role="script_writer", task="...", context="...")
        # Output è guaranteed to be in italiano (or corrected if wrong)
    """
    validator = LanguageValidator(target_language, strict_mode)

    def wrapped_llm_fn(role: str, task: str, context: str = "", **kwargs):
        """Wrapped LLM function con language validation."""

        # Call original LLM
        llm_output = llm_generate_fn(role, task, context, **kwargs)

        # Validate and correct if needed
        validated_output = validator.ensure_language_consistency(
            llm_output,
            llm_generate_fn,
            context=context,
            component_name=f"{component_name}:{role}"
        )

        return validated_output

    return wrapped_llm_fn


def validate_and_fix_enum_fields(
    json_output: Dict,
    llm_generate_fn: Callable,
    target_language: str,
    enum_specs: Dict[str, list],
    component_name: str = "unknown"
) -> Dict:
    """
    Validate and fix enum fields in JSON output using AI correction (Layer 2).

    This function checks if enum fields contain correct English values,
    even when the workspace language is different. If wrong values detected,
    uses LLM to intelligently map them to correct enum values.

    Args:
        json_output: Parsed JSON dict from LLM
        llm_generate_fn: LLM function for correction
        target_language: Workspace language (e.g., "it", "en")
        enum_specs: Dict mapping field name → list of valid values
                   Example: {"format": ["tutorial", "analysis", "alert"]}
        component_name: Component name for logging

    Returns:
        Corrected JSON dict with valid enum values

    Example:
        >>> json_output = {"format": "analisi", "angle": "educazione"}
        >>> enum_specs = {
        ...     "format": ["tutorial", "analysis", "alert", "comparison"],
        ...     "angle": ["risk", "opportunity", "education", "history"]
        ... }
        >>> corrected = validate_and_fix_enum_fields(
        ...     json_output, llm_fn, "it", enum_specs, "editorial_strategist"
        ... )
        >>> print(corrected)
        {"format": "analysis", "angle": "education"}  # Fixed!
    """
    logger.info(f"=" * 70)
    logger.info(f"ENUM VALIDATION (Layer 2): {component_name}")
    logger.info(f"=" * 70)

    # Check each enum field
    invalid_fields = {}
    for field_name, allowed_values in enum_specs.items():
        if field_name in json_output:
            actual_value = json_output[field_name]

            # Check if value is in allowed list (case-insensitive)
            if actual_value.lower() not in [v.lower() for v in allowed_values]:
                invalid_fields[field_name] = {
                    "current": actual_value,
                    "allowed": allowed_values
                }
                logger.warning(f"  ❌ Invalid enum: {field_name} = '{actual_value}'")
                logger.warning(f"     Allowed: {', '.join(allowed_values)}")

    # If all valid, return as-is
    if not invalid_fields:
        logger.info(f"  ✅ All enum fields valid!")
        return json_output

    # Attempt AI-driven enum correction
    logger.info(f"  🔄 Attempting AI-driven enum correction...")
    logger.info(f"     Found {len(invalid_fields)} invalid enum field(s)")

    # Build correction prompt
    correction_prompt = f"""
You are a data validator. The following JSON output has INCORRECT enum field values.

WORKSPACE LANGUAGE: {LANGUAGE_NAMES.get(target_language, target_language)}

CURRENT JSON OUTPUT (with errors):
{json.dumps(json_output, indent=2, ensure_ascii=False)}

VALIDATION ERRORS:
{chr(10).join([
    f"- Field '{field}': Current value '{info['current']}' is INVALID. Must be ONE of: {', '.join(info['allowed'])}"
    for field, info in invalid_fields.items()
])}

YOUR TASK:
Fix ONLY the enum fields with correct English values from the allowed lists above.

CORRECTION RULES:
1. ✅ Map semantic meaning to correct English enum value
   Example: "educazione" (Italian) → "education" (English enum)
   Example: "analisi" (Italian) → "analysis" (English enum)

2. ✅ Preserve ALL other fields unchanged (especially text fields in workspace language)

3. ✅ Output format: Valid JSON object (same structure as input)

4. ❌ DO NOT translate text fields (serie_concept, cta_specific, reasoning_summary)
   These SHOULD remain in {LANGUAGE_NAMES.get(target_language, target_language)}!

5. ✅ ONLY fix the enum fields: {', '.join(invalid_fields.keys())}

CORRECTED JSON OUTPUT (copy all fields, fix enums only):
"""

    try:
        # Call LLM for intelligent enum correction
        corrected_json_str = llm_generate_fn(
            role="enum_validator",
            task=correction_prompt,
            context="",
            style_hints={"temperature": 0.1}  # Very low temp for deterministic correction
        )

        # Parse corrected JSON
        import json
        import re

        # Try direct JSON parse
        try:
            corrected_json = json.loads(corrected_json_str)
        except json.JSONDecodeError:
            # Extract from markdown code block
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', corrected_json_str, re.DOTALL)
            if json_match:
                corrected_json = json.loads(json_match.group(1))
            else:
                # Try to find JSON object
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', corrected_json_str, re.DOTALL)
                if json_match:
                    corrected_json = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not extract JSON from LLM response")

        # Validate correction
        all_valid = True
        for field_name, allowed_values in enum_specs.items():
            if field_name in corrected_json:
                new_value = corrected_json[field_name]
                if new_value.lower() not in [v.lower() for v in allowed_values]:
                    all_valid = False
                    logger.warning(f"  ⚠️ Correction failed for {field_name}: still invalid '{new_value}'")
                else:
                    if field_name in invalid_fields:
                        logger.info(f"  ✓ Fixed: {field_name} = '{invalid_fields[field_name]['current']}' → '{new_value}'")

        if all_valid:
            logger.info(f"  ✅ Enum correction SUCCESSFUL")
            return corrected_json
        else:
            logger.warning(f"  ⚠️ Enum correction incomplete, using best effort result")
            return corrected_json

    except Exception as e:
        logger.error(f"  ❌ AI-driven enum correction failed: {e}")
        logger.warning(f"     Falling back to Layer 3 (hard-coded normalization)")

        # Log fallback
        log_fallback(
            component=f"LANGUAGE_VALIDATOR_ENUM_CORRECTION_{component_name.upper()}",
            fallback_type="AI_ENUM_CORRECTION_FAILED",
            reason=f"AI-driven enum correction failed: {e}. Will fallback to Layer 3.",
            impact="MEDIUM"
        )

        # Return original (Layer 3 will handle it)
        return json_output


# Example usage
if __name__ == '__main__':
    # Mock LLM function for testing
    def mock_llm(role: str, task: str, context: str = "", **kwargs):
        """Mock LLM che ritorna sempre inglese (per testare correction)."""
        return "Hello world! This is a test message in English."

    # Test language validator
    validator = LanguageValidator(target_language="it", strict_mode=True)

    print("\n" + "=" * 70)
    print("DEMO: Language Validator")
    print("=" * 70)

    # Test 1: Detect language
    italian_text = "Ciao mondo! Questo è un test."
    english_text = "Hello world! This is a test."

    print("\n1. LANGUAGE DETECTION")
    lang_it, conf_it = validator.detect_language(italian_text)
    print(f"   Italian text detected as: {lang_it} (confidence: {conf_it:.2f})")

    lang_en, conf_en = validator.detect_language(english_text)
    print(f"   English text detected as: {lang_en} (confidence: {conf_en:.2f})")

    # Test 2: Language consistency score
    print("\n2. CONSISTENCY SCORE")
    score_it = validator.calculate_language_consistency_score(italian_text, "it")
    print(f"   Italian text vs target 'it': {score_it:.2f}")

    score_en = validator.calculate_language_consistency_score(english_text, "it")
    print(f"   English text vs target 'it': {score_en:.2f}")

    # Test 3: Language enforcement (with mock LLM)
    print("\n3. LANGUAGE ENFORCEMENT (Mock)")
    wrong_output = "This is wrong language output"
    print(f"   Input: {wrong_output}")
    print(f"   Target: Italian")

    # Note: In real usage, mock_llm would actually translate
    # Here we just demo the flow
    print(f"   (Mock LLM would translate to Italian)")
