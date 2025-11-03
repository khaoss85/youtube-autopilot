"""
Centralized logging module for yt_autopilot.
All modules should import logger from here.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "yt_autopilot",
    level: Optional[str] = None,
    log_file: Optional[Path] = None
) -> logging.Logger:
    """
    Creates and configures a logger instance.

    Args:
        name: Logger name (default: "yt_autopilot")
        level: Log level string ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
               If None, reads from config or defaults to INFO
        log_file: Optional path to log file. If provided, logs to both file and console.

    Returns:
        Configured logger instance
    """
    # Determine log level
    if level is None:
        # Avoid circular import by lazy loading
        try:
            from yt_autopilot.core.config import get_config
            config = get_config()
            level = config.get("LOG_LEVEL", "INFO")
        except ImportError:
            level = "INFO"

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with formatting (stderr = best practice for logs)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)

    # Formatter with timestamp
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Global logger instance - import this from other modules
logger = setup_logger()


# ============================================================================
# FALLBACK LOGGING SYSTEM - SEMPRE USARE PER LOGICA DI FALLBACK
# ============================================================================
# Quando implementi logica di fallback (es. LLM fallisce → logica alternativa),
# USA SEMPRE questa funzione per tracciare l'evento.
#
# Questo permette di:
# - Validare qualità test (grep "🚨 FALLBACK" test.log)
# - Monitorare fallback rate in produzione
# - Debug efficiente (identificare cause fallback)
#
# CONVENZIONI: Vedi DEVELOPMENT_CONVENTIONS.md per dettagli completi
# ============================================================================

def log_fallback(
    component: str,
    fallback_type: str,
    reason: str,
    impact: str = "MEDIUM"
) -> None:
    """
    🚨 STANDARDIZED FALLBACK LOGGING - ALWAYS USE FOR FALLBACK LOGIC

    Standardized logging for fallback scenarios to distinguish real vs. fallback output.

    This function helps identify when the pipeline uses fallback/mock data instead of
    real LLM-generated content, making it easy to validate test quality.

    Args:
        component: Component name (e.g., "LLM_CURATION", "MONETIZATION_QA")
        fallback_type: Type of fallback (e.g., "MOMENTUM_ONLY", "RULE_BASED")
        reason: Why fallback was triggered (e.g., "LLM call failed")
        impact: Impact level - "LOW", "MEDIUM", "HIGH" (default: "MEDIUM")
                - LOW: Minor degradation, barely noticeable
                - MEDIUM: Moderate degradation, output still usable
                - HIGH: Significant degradation, output quality affected

    Format: 🚨 FALLBACK: [COMPONENT] [TYPE] - [REASON] (impact: [IMPACT])

    Example:
        >>> log_fallback("LLM_CURATION", "MOMENTUM_ONLY", "LLM call failed", impact="HIGH")
        # Logs: 🚨 FALLBACK: LLM_CURATION MOMENTUM_ONLY - LLM call failed (impact: HIGH)

    Usage for test validation:
        - Grep for fallbacks: grep "🚨 FALLBACK" test.log
        - Check if test is "pure": grep -c "🚨 FALLBACK" test.log (should be 0)
        - Monitor fallback rate: grep "🚨 FALLBACK" *.log | wc -l
    """
    message = f"🚨 FALLBACK: {component} {fallback_type} - {reason} (impact: {impact})"
    logger.warning(message)


# ============================================================================
# LOG TRUNCATION UTILITY - USE FOR CONSISTENT LOG MESSAGE FORMATTING
# ============================================================================
# Centralized truncation utility to maintain consistent, readable log messages
# across the entire codebase without flooding terminal output.
# ============================================================================

def truncate_for_log(
    text: Optional[str],
    max_length: int,
    suffix: str = "..."
) -> str:
    """
    Safely truncate text for logging with ellipsis.

    Use this utility instead of manual string slicing (e.g., text[:100])
    to ensure consistent truncation behavior across the codebase.

    Args:
        text: Text to truncate (can be None)
        max_length: Maximum length before truncation
        suffix: String to append when truncated (default: "...")

    Returns:
        Truncated text with suffix if needed, or original text if short enough.
        Returns empty string if text is None.

    Example:
        >>> truncate_for_log("This is a long text", 10)
        "This is a ..."
        >>> truncate_for_log("Short", 10)
        "Short"
        >>> truncate_for_log(None, 10)
        ""
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length].rstrip() + suffix
