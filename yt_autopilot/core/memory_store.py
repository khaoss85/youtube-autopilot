"""
Channel brand memory and compliance history management.
Stores and retrieves persistent channel identity and recent content history.
"""

import json
from pathlib import Path
from typing import Dict, List

from yt_autopilot.core.config import get_memory_path
from yt_autopilot.core.logger import logger
from yt_autopilot.core.schemas import ChannelMemory


# Default memory structure if file doesn't exist
DEFAULT_MEMORY = {
    "brand_tone": "Positivo, diretto, niente volgarità",
    "visual_style": "Ritmo alto, colori caldi, testo grande in sovrimpressione stile Shorts verticali",
    "banned_topics": [
        "insulti personali",
        "politica nazionale aggressiva",
        "promesse di cure mediche garantite",
        "uso di musica protetta da copyright"
    ],
    "recent_titles": []
}


def load_memory() -> Dict:
    """
    Loads channel memory from JSON file.
    If file doesn't exist, creates it with default values.

    Returns:
        Dict containing brand_tone, visual_style, banned_topics, recent_titles
    """
    memory_path = get_memory_path()

    if not memory_path.exists():
        logger.info(f"Memory file not found at {memory_path}, creating with defaults")
        save_memory(DEFAULT_MEMORY)
        return DEFAULT_MEMORY.copy()

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            memory = json.load(f)

        # Validate structure using Pydantic
        ChannelMemory(**memory)

        logger.debug(f"Loaded memory from {memory_path}")
        return memory

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to load memory from {memory_path}: {e}")
        logger.warning("Falling back to default memory")
        return DEFAULT_MEMORY.copy()


def save_memory(memory: Dict) -> None:
    """
    Saves channel memory to JSON file.
    Validates structure before saving.

    Args:
        memory: Dictionary containing memory data

    Raises:
        ValueError: If memory doesn't match expected schema
    """
    # Validate using Pydantic
    ChannelMemory(**memory)

    memory_path = get_memory_path()
    memory_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved memory to {memory_path}")

    except Exception as e:
        logger.error(f"Failed to save memory to {memory_path}: {e}")
        raise


def get_brand_tone(memory: Dict) -> str:
    """
    Extracts brand tone from memory.

    Args:
        memory: Memory dictionary

    Returns:
        Brand tone string
    """
    return memory.get("brand_tone", DEFAULT_MEMORY["brand_tone"])


def get_visual_style(memory: Dict) -> str:
    """
    Extracts visual style from memory.

    Args:
        memory: Memory dictionary

    Returns:
        Visual style description
    """
    return memory.get("visual_style", DEFAULT_MEMORY["visual_style"])


def get_banned_topics(memory: Dict) -> List[str]:
    """
    Extracts list of banned/restricted topics for compliance.

    Args:
        memory: Memory dictionary

    Returns:
        List of banned topic strings
    """
    return memory.get("banned_topics", DEFAULT_MEMORY["banned_topics"].copy())


def get_recent_titles(memory: Dict) -> List[str]:
    """
    Extracts list of recently used video titles.

    Args:
        memory: Memory dictionary

    Returns:
        List of recent title strings
    """
    return memory.get("recent_titles", [])


def append_recent_title(memory: Dict, title: str, max_titles: int = 50) -> None:
    """
    Adds a new title to recent titles history.
    Maintains a rolling window of most recent titles.

    Args:
        memory: Memory dictionary (will be modified in place)
        title: New video title to add
        max_titles: Maximum number of titles to keep in history (default: 50)
    """
    if "recent_titles" not in memory:
        memory["recent_titles"] = []

    memory["recent_titles"].append(title)

    # Keep only most recent titles
    if len(memory["recent_titles"]) > max_titles:
        memory["recent_titles"] = memory["recent_titles"][-max_titles:]

    logger.debug(f"Added title to memory: '{title}' (total: {len(memory['recent_titles'])})")
