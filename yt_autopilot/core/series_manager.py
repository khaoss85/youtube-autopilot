"""
Series Manager: Manages video series formats, templates, and asset caching.

Step 07.5: Format Engine - Enables repeatable video structures with
intro/outro reuse and segment-based scriptwriting.

This module handles:
- Serie detection from video topic
- Format template loading from YAML configs
- Intro/outro video caching for series reuse
- Series-specific asset directory management
"""

import os
import shutil
import yaml
from pathlib import Path
from typing import Optional, Dict
from yt_autopilot.core.schemas import SeriesFormat, SeriesSegment
from yt_autopilot.core.config import get_config
from yt_autopilot.core.logger import logger


# Serie detection keyword mapping
# Maps topic keywords to serie_id
SERIE_KEYWORDS = {
    "tech_tutorial": [
        "programmazione", "python", "ai tools", "produttività", "tutorial",
        "tecnologia", "software", "coding", "developer", "api"
    ],
    "news_flash": [
        "notizie", "breaking", "aggiornamento", "nuovo", "annuncio",
        "rilascio", "update", "release", "lancio"
    ],
    "how_to": [
        "come fare", "guida", "step by step", "imparare", "corso",
        "facile", "principianti", "spiegazione", "capire"
    ]
}

DEFAULT_SERIE = "tech_tutorial"


def detect_serie(topic: str) -> str:
    """
    Detects the appropriate series format based on topic keywords.

    Step 07.5: Maps video topics to serie_id for format template selection.

    Algorithm:
    1. Normalize topic to lowercase
    2. Check for keyword matches in SERIE_KEYWORDS
    3. Return first matching serie_id
    4. Fallback to DEFAULT_SERIE if no match

    Args:
        topic: Video topic/title (e.g., "Programmazione Python per principianti 2025")

    Returns:
        serie_id (e.g., "tech_tutorial", "news_flash", "how_to")

    Example:
        >>> detect_serie("Programmazione Python per principianti")
        'tech_tutorial'
        >>> detect_serie("Come fare video con AI tools")
        'how_to'
        >>> detect_serie("Breaking: Nuovo GPT-5 rilasciato")
        'news_flash'
    """
    topic_lower = topic.lower()

    # Check each serie's keywords
    for serie_id, keywords in SERIE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in topic_lower:
                logger.info(f"Serie detected: '{serie_id}' (matched keyword: '{keyword}')")
                return serie_id

    # Fallback to default
    logger.info(f"Serie not detected, using default: '{DEFAULT_SERIE}'")
    return DEFAULT_SERIE


def load_format(serie_id: str) -> SeriesFormat:
    """
    Loads series format template from YAML configuration.

    Step 07.5: Reads YAML config and constructs SeriesFormat object.

    YAML structure:
    ```yaml
    serie_id: tech_tutorial
    name: "Tech Tutorial"
    description: "Tutorial su tecnologia e innovazione"
    intro_duration_seconds: 2
    intro_veo_prompt: "Modern tech intro..."
    outro_duration_seconds: 3
    outro_veo_prompt: "Tech outro..."
    segments:
      - type: hook
        name: "Opening Hook"
        target_duration_min: 3
        target_duration_max: 5
        description: "..."
    total_target_duration_min: 20
    total_target_duration_max: 30
    ```

    Args:
        serie_id: Serie identifier (e.g., "tech_tutorial")

    Returns:
        SeriesFormat object with template configuration

    Raises:
        FileNotFoundError: If YAML config doesn't exist
        ValueError: If YAML structure is invalid
    """
    config_dir = Path(__file__).parent.parent.parent / "config" / "series_formats"
    yaml_path = config_dir / f"{serie_id}.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Series format config not found: {yaml_path}\n"
            f"Available series: {list(SERIE_KEYWORDS.keys())}"
        )

    logger.info(f"Loading series format: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Parse segments
    segments = []
    for seg_data in data.get("segments", []):
        segment = SeriesSegment(
            type=seg_data["type"],
            name=seg_data["name"],
            target_duration_min=seg_data["target_duration_min"],
            target_duration_max=seg_data["target_duration_max"],
            description=seg_data["description"]
        )
        segments.append(segment)

    # Construct SeriesFormat
    series_format = SeriesFormat(
        serie_id=data["serie_id"],
        name=data["name"],
        description=data["description"],
        intro_duration_seconds=data.get("intro_duration_seconds", 2),
        intro_veo_prompt=data["intro_veo_prompt"],
        outro_duration_seconds=data.get("outro_duration_seconds", 3),
        outro_veo_prompt=data["outro_veo_prompt"],
        segments=segments,
        total_target_duration_min=data.get("total_target_duration_min", 20),
        total_target_duration_max=data.get("total_target_duration_max", 30)
    )

    logger.info(
        f"✓ Loaded series format: {series_format.name} "
        f"({len(series_format.segments)} segments)"
    )

    return series_format


def _get_series_cache_dir(serie_id: str) -> Path:
    """
    Returns the cache directory for a series.

    Step 07.5: Series-level cache for reusable intro/outro assets.

    Directory structure:
    ```
    output/
      .series_cache/
        tech_tutorial/
          intro.mp4
          outro.mp4
        news_flash/
          intro.mp4
          outro.mp4
    ```

    Args:
        serie_id: Serie identifier

    Returns:
        Path to series cache directory (created if doesn't exist)
    """
    config = get_config()
    base_output = config.get("OUTPUT_DIR", Path("output"))
    cache_dir = Path(base_output) / ".series_cache" / serie_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cached_intro(serie_id: str) -> Optional[str]:
    """
    Retrieves cached intro video path for a series if it exists.

    Step 07.5: Reuses intro videos across all videos in the same series.

    Args:
        serie_id: Serie identifier

    Returns:
        Path to cached intro video, or None if not cached
    """
    cache_dir = _get_series_cache_dir(serie_id)
    intro_path = cache_dir / "intro.mp4"

    if intro_path.exists():
        logger.info(f"✓ Found cached intro for serie '{serie_id}': {intro_path}")
        return str(intro_path)

    logger.info(f"No cached intro for serie '{serie_id}'")
    return None


def get_cached_outro(serie_id: str) -> Optional[str]:
    """
    Retrieves cached outro video path for a series if it exists.

    Step 07.5: Reuses outro videos across all videos in the same series.

    Args:
        serie_id: Serie identifier

    Returns:
        Path to cached outro video, or None if not cached
    """
    cache_dir = _get_series_cache_dir(serie_id)
    outro_path = cache_dir / "outro.mp4"

    if outro_path.exists():
        logger.info(f"✓ Found cached outro for serie '{serie_id}': {outro_path}")
        return str(outro_path)

    logger.info(f"No cached outro for serie '{serie_id}'")
    return None


def cache_intro(serie_id: str, source_path: str) -> str:
    """
    Caches an intro video for series-wide reuse.

    Step 07.5: Copies generated intro to series cache for future videos.

    Args:
        serie_id: Serie identifier
        source_path: Path to generated intro video

    Returns:
        Path to cached intro video
    """
    cache_dir = _get_series_cache_dir(serie_id)
    intro_path = cache_dir / "intro.mp4"

    # Copy source to cache
    shutil.copy2(source_path, intro_path)

    logger.info(f"✓ Cached intro for serie '{serie_id}': {intro_path}")
    return str(intro_path)


def cache_outro(serie_id: str, source_path: str) -> str:
    """
    Caches an outro video for series-wide reuse.

    Step 07.5: Copies generated outro to series cache for future videos.

    Args:
        serie_id: Serie identifier
        source_path: Path to generated outro video

    Returns:
        Path to cached outro video
    """
    cache_dir = _get_series_cache_dir(serie_id)
    outro_path = cache_dir / "outro.mp4"

    # Copy source to cache
    shutil.copy2(source_path, outro_path)

    logger.info(f"✓ Cached outro for serie '{serie_id}': {outro_path}")
    return str(outro_path)


def list_available_series() -> Dict[str, str]:
    """
    Lists all available series formats with descriptions.

    Returns:
        Dict mapping serie_id to series name
    """
    config_dir = Path(__file__).parent.parent.parent / "config" / "series_formats"

    if not config_dir.exists():
        return {}

    series_list = {}

    for yaml_file in config_dir.glob("*.yaml"):
        serie_id = yaml_file.stem
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                series_list[serie_id] = data.get("name", serie_id)
        except Exception as e:
            logger.warning(f"Failed to load series {yaml_file}: {e}")

    return series_list
