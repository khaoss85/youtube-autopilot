"""
LLM Router: Centralized Multi-Provider LLM Access (Step 06-pre)

This module provides a unified interface for calling LLM providers (Anthropic Claude, OpenAI GPT)
with automatic fallback and error handling.

Architecture Decision:
- This is a SERVICE layer module (services/llm_router.py)
- AGENTS do NOT import this directly (violates layering rules)
- PIPELINE layer (build_video_package) will call llm_router and pass results to agents
- This maintains agent purity: agents remain deterministic pure functions

Provider Priority:
1. Anthropic Claude (if LLM_ANTHROPIC_API_KEY is set)
2. OpenAI GPT (if LLM_OPENAI_API_KEY is set)
3. Fallback to deterministic placeholder if no keys or API fails

Usage:
    from yt_autopilot.services.llm_router import generate_text

    result = generate_text(
        role="script_writer",
        task="Generate a viral hook for YouTube Shorts",
        context="Topic: AI video generation tools",
        style_hints={"brand_tone": "casual", "target_audience": "tech enthusiasts"}
    )
"""

from typing import Dict, Any, Optional
from yt_autopilot.core.logger import logger, truncate_for_log, log_fallback
from yt_autopilot.core.config import (
    get_llm_anthropic_key,
    get_llm_openai_key,
    LOG_TRUNCATE_TASK,
    LOG_TRUNCATE_CONTENT
)


def generate_text(
    role: str,
    task: str,
    context: str,
    style_hints: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate text using LLM with automatic provider selection and fallback.

    Args:
        role: Agent role identifier (e.g., "script_writer", "seo_manager", "trend_hunter")
              Used for logging and future per-agent model selection
        task: High-level instruction for the LLM (e.g., "generate hook", "optimize title")
        context: Specific content to process (e.g., video plan, key points, draft text)
        style_hints: Optional dict with branding/style info
                     Keys: brand_tone, banned_topics, target_audience, etc.

    Returns:
        Generated text string
        On failure: Returns fallback string "[LLM_FALLBACK] <summary>"

    Behavior:
        1. Try Anthropic Claude if LLM_ANTHROPIC_API_KEY is set
        2. Fall back to OpenAI GPT if LLM_OPENAI_API_KEY is set
        3. Return graceful fallback if both fail or no keys

    Example:
        >>> result = generate_text(
        ...     role="script_writer",
        ...     task="write opening hook",
        ...     context="Video about: AI automation for YouTube",
        ...     style_hints={"brand_tone": "casual", "target_audience": "creators"}
        ... )
        >>> print(result)
        "Want to automate your YouTube channel with AI? Here's how..."

    TODO (Future Enhancement):
        - Per-agent model selection (e.g., ScriptWriter → GPT-4, SeoManager → Claude)
        - Token usage tracking and logging
        - Caching frequently used prompts
        - Streaming support for long-form generation
    """
    logger.info(f"LLM Router: Generating text for role={role}, task={truncate_for_log(task, LOG_TRUNCATE_TASK)}")

    # Build style context if provided
    style_context = ""
    if style_hints:
        style_context = "\n\nStyle Guidelines:\n"
        for key, value in style_hints.items():
            style_context += f"- {key}: {value}\n"

    # Build full prompt
    full_prompt = f"Task: {task}\n\nContext:\n{context}{style_context}"

    # Use OpenAI GPT as primary provider (Fase 1-BIS-2: Anthropic removed, will be re-added in future for per-agent selection)
    openai_key = get_llm_openai_key()
    if openai_key:
        logger.info("  Calling OpenAI GPT...")
        result = _call_openai(openai_key, role, full_prompt)
        if result:
            logger.info(f"  ✓ OpenAI GPT succeeded ({len(result)} chars)")
            return result
        else:
            # 🚨 CRITICAL: Log OpenAI fallback for visibility
            log_fallback(
                component="LLM_ROUTER",
                fallback_type="OPENAI_FAILED",
                reason="OpenAI API call failed or returned None",
                impact="CRITICAL"
            )
            logger.warning("  ✗ OpenAI GPT failed, using deterministic fallback...")

    # No key or provider failed - graceful fallback
    # 🚨 CRITICAL: Log no provider fallback for visibility
    log_fallback(
        component="LLM_ROUTER",
        fallback_type="NO_PROVIDER",
        reason="No LLM API keys configured (LLM_OPENAI_API_KEY missing)",
        impact="CRITICAL"
    )
    logger.warning("  No LLM provider available - returning fallback")
    fallback = _generate_fallback(role, task, context)
    logger.info(f"  Fallback generated: {truncate_for_log(fallback, LOG_TRUNCATE_CONTENT)}")
    return fallback


def _call_anthropic(api_key: str, role: str, prompt: str) -> Optional[str]:
    """
    Call Anthropic Claude API.

    Args:
        api_key: Anthropic API key
        role: Agent role (for logging)
        prompt: Full prompt text

    Returns:
        Generated text or None on failure
    """
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        # Call Claude with appropriate model
        # Using Claude 3.5 Sonnet for balance of speed and quality
        response = client.messages.create(
            model="claude-3-5-sonnet-20241220",  # Latest Claude model (updated from deprecated 20241022)
            max_tokens=2048,
            temperature=0.7,  # Moderate creativity
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract text from response
        if response.content and len(response.content) > 0:
            text = response.content[0].text
            return text.strip()

        return None

    except ImportError:
        # 🚨 Log Anthropic SDK missing fallback
        log_fallback(
            component="LLM_ROUTER_ANTHROPIC",
            fallback_type="SDK_NOT_INSTALLED",
            reason="anthropic package not installed",
            impact="HIGH"
        )
        logger.error("  Anthropic SDK not installed - run: pip install anthropic")
        return None
    except Exception as e:
        # 🚨 Log Anthropic API error fallback
        log_fallback(
            component="LLM_ROUTER_ANTHROPIC",
            fallback_type="API_ERROR",
            reason=str(e),
            impact="HIGH"
        )
        logger.error(f"  Anthropic API error: {e}")
        return None


def _call_openai(api_key: str, role: str, prompt: str) -> Optional[str]:
    """
    Call OpenAI GPT API.

    Args:
        api_key: OpenAI API key
        role: Agent role (for logging)
        prompt: Full prompt text

    Returns:
        Generated text or None on failure
    """
    try:
        import openai

        client = openai.OpenAI(api_key=api_key)

        # Call GPT with appropriate model
        # Using GPT-4o for best quality/speed balance
        response = client.chat.completions.create(
            model="gpt-4o",  # Latest GPT-4 optimized model
            messages=[
                {
                    "role": "system",
                    "content": f"You are a helpful AI assistant acting as a {role} for a YouTube automation system."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=2048,
            temperature=0.7  # Moderate creativity
        )

        # Extract text from response
        if response.choices and len(response.choices) > 0:
            text = response.choices[0].message.content
            if text:
                return text.strip()

        return None

    except ImportError:
        # 🚨 CRITICAL: Log OpenAI SDK missing fallback
        log_fallback(
            component="LLM_ROUTER_OPENAI",
            fallback_type="SDK_NOT_INSTALLED",
            reason="openai package not installed",
            impact="CRITICAL"
        )
        logger.error("  OpenAI SDK not installed - run: pip install openai")
        return None
    except Exception as e:
        # 🚨 CRITICAL: Log OpenAI API error fallback
        log_fallback(
            component="LLM_ROUTER_OPENAI",
            fallback_type="API_ERROR",
            reason=str(e),
            impact="CRITICAL"
        )
        logger.error(f"  OpenAI API error: {e}")
        return None


def _generate_fallback(role: str, task: str, context: str) -> str:
    """
    Generate deterministic fallback text when LLM providers are unavailable.

    This ensures the system continues to work even without LLM access,
    though with reduced quality.

    Args:
        role: Agent role
        task: Task description
        context: Context information

    Returns:
        Fallback text with [LLM_FALLBACK] prefix
    """
    # Extract key information from context for minimal fallback
    context_preview = truncate_for_log(context.replace("\n", " "), LOG_TRUNCATE_CONTENT)

    fallback = f"[LLM_FALLBACK] {task}\n\nBased on: {context_preview}"

    return fallback


# =============================================================================
# TODO: Future Enhancements for Production
# =============================================================================

# TODO: Per-Agent Model Selection
#
# Different agents may benefit from different models:
#
# def get_model_for_agent(role: str) -> tuple[str, str]:
#     """
#     Return (provider, model_name) for specific agent role.
#
#     Examples:
#     - script_writer → ("openai", "gpt-4o") # Creative writing
#     - seo_manager → ("anthropic", "claude-3-5-sonnet") # Analytical
#     - quality_reviewer → ("anthropic", "claude-3-opus") # Detailed analysis
#
#     This allows optimization of cost vs quality per use case.
#     """
#     pass
#
# TODO: Token Usage Tracking
#
# Track and log token consumption for cost monitoring:
#
# def log_token_usage(role: str, provider: str, input_tokens: int, output_tokens: int):
#     """Log token usage to datastore for cost analysis."""
#     pass
#
# TODO: Prompt Caching
#
# Cache frequently used prompts (e.g., system prompts, style guidelines):
#
# _prompt_cache = {}
#
# def get_cached_prompt(cache_key: str) -> Optional[str]:
#     """Retrieve cached prompt to save tokens."""
#     return _prompt_cache.get(cache_key)
#
# TODO: Rate Limiting
#
# Implement rate limiting to avoid API quotas:
#
# from time import sleep
# from datetime import datetime
#
# _last_call_time = {}
#
# def rate_limit(provider: str, min_interval_seconds: float = 0.1):
#     """Ensure minimum interval between API calls."""
#     pass
