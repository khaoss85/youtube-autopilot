"""
Core configuration module.
Loads environment variables and provides centralized config access.
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent.parent
_env_path = _project_root / ".env"
load_dotenv(_env_path)


def get_config() -> Dict[str, Any]:
    """
    Returns configuration dictionary with all necessary API keys and settings.

    Returns:
        Dict containing:
            - LLM_API_KEY: API key for LLM service (e.g., OpenAI, Anthropic)
            - VEO_API_KEY: API key for Google Veo video generation
            - YOUTUBE_CLIENT_ID: YouTube OAuth client ID
            - YOUTUBE_CLIENT_SECRET: YouTube OAuth client secret
            - YOUTUBE_REFRESH_TOKEN: YouTube OAuth refresh token
            - OUTPUT_DIR: Directory for final video outputs
            - TEMP_DIR: Directory for temporary files during processing
            - PROJECT_ROOT: Absolute path to project root
    """
    config = {
        # API Keys
        "LLM_API_KEY": os.getenv("LLM_API_KEY", ""),
        "VEO_API_KEY": os.getenv("VEO_API_KEY", ""),

        # YouTube OAuth
        "YOUTUBE_CLIENT_ID": os.getenv("YOUTUBE_CLIENT_ID", ""),
        "YOUTUBE_CLIENT_SECRET": os.getenv("YOUTUBE_CLIENT_SECRET", ""),
        "YOUTUBE_REFRESH_TOKEN": os.getenv("YOUTUBE_REFRESH_TOKEN", ""),

        # Directory paths
        "OUTPUT_DIR": Path(os.getenv("OUTPUT_DIR", "./output")).resolve(),
        "TEMP_DIR": Path(os.getenv("TEMP_DIR", "./tmp")).resolve(),
        "PROJECT_ROOT": _project_root.resolve(),

        # Optional settings
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "MEMORY_FILE": os.getenv("MEMORY_FILE", "channel_memory.json"),
    }

    # Ensure directories exist
    config["OUTPUT_DIR"].mkdir(parents=True, exist_ok=True)
    config["TEMP_DIR"].mkdir(parents=True, exist_ok=True)

    return config


def validate_config() -> bool:
    """
    Validates that all required configuration values are present.

    Returns:
        True if all required keys are present and non-empty, False otherwise.
    """
    config = get_config()
    required_keys = [
        "LLM_API_KEY",
        "VEO_API_KEY",
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REFRESH_TOKEN",
    ]

    missing = [key for key in required_keys if not config.get(key)]

    if missing:
        return False

    return True


def get_memory_path() -> Path:
    """
    Returns the full path to the channel memory JSON file.

    Returns:
        Path object pointing to channel_memory.json
    """
    config = get_config()
    return config["PROJECT_ROOT"] / config["MEMORY_FILE"]
