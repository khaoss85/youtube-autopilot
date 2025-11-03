"""
Core module: Shared data models, configuration, logging, and channel memory.
This module has no dependencies on other yt_autopilot modules.
"""

from yt_autopilot.core.config import (
    get_config,
    validate_config,
    get_memory_path,
    get_output_dir,
    get_temp_dir,
    get_llm_anthropic_key,
    get_llm_openai_key,
    get_env,
)
from yt_autopilot.core.logger import logger
from yt_autopilot.core import schemas
from yt_autopilot.core.memory_store import (
    load_memory,
    save_memory,
    get_brand_tone,
    get_visual_style,
    get_banned_topics,
    get_recent_titles,
    append_recent_title,
)

__all__ = [
    # Config
    "get_config",
    "validate_config",
    "get_memory_path",
    "get_output_dir",
    "get_temp_dir",
    "get_llm_anthropic_key",
    "get_llm_openai_key",
    "get_env",
    # Logger
    "logger",
    # Schemas (export the module)
    "schemas",
    # Memory store
    "load_memory",
    "save_memory",
    "get_brand_tone",
    "get_visual_style",
    "get_banned_topics",
    "get_recent_titles",
    "append_recent_title",
]
