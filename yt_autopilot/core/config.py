"""
Core configuration module.
Loads environment variables and provides centralized config access.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
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


def get_output_dir() -> Path:
    """
    Returns the output directory path for final videos.

    Returns:
        Path object pointing to OUTPUT_DIR
    """
    config = get_config()
    return config["OUTPUT_DIR"]


def get_temp_dir() -> Path:
    """
    Returns the temporary directory path for processing files.

    Returns:
        Path object pointing to TEMP_DIR
    """
    config = get_config()
    return config["TEMP_DIR"]


# ============================================================================
# LLM Provider Configuration (Step 06-pre: Multi-Provider Support)
# ============================================================================

def get_llm_anthropic_key() -> Optional[str]:
    """
    Returns the Anthropic Claude API key if configured.

    Returns:
        API key string if LLM_ANTHROPIC_API_KEY is set in .env, None otherwise

    Usage:
        Used by services/llm_router.py for Anthropic Claude API calls
    """
    key = os.getenv("LLM_ANTHROPIC_API_KEY", "")
    if not key:
        return None
    return key


def get_llm_openai_key() -> Optional[str]:
    """
    Returns the OpenAI API key if configured.

    Returns:
        API key string if LLM_OPENAI_API_KEY is set in .env, None otherwise

    Usage:
        Used by services/llm_router.py for OpenAI GPT API calls
    """
    key = os.getenv("LLM_OPENAI_API_KEY", "")
    if not key:
        return None
    return key


def get_veo_api_key() -> Optional[str]:
    """
    Returns the Veo/Vertex AI API key if configured.

    Returns:
        API key string if VEO_API_KEY is set in .env, None otherwise

    Usage:
        Used by services/video_gen_service.py for Google Veo/Vertex AI video generation

    Note:
        This can be either:
        - A direct API key (e.g., from Google AI Studio)
        - A service account key for Vertex AI
        - Path to a service account JSON file
    """
    key = os.getenv("VEO_API_KEY", "")
    if not key:
        return None
    return key


def get_openai_video_key() -> Optional[str]:
    """
    Returns the OpenAI Video API key if configured.

    Step 07.2: Added for Sora-style video generation support

    Returns:
        API key string if OPENAI_VIDEO_API_KEY is set in .env, None otherwise

    Usage:
        Used by services/video_gen_service.py for OpenAI Sora-style video generation
        Falls back to Veo if not configured

    Note:
        This is for OpenAI's video generation API (Sora or similar).
        May use the same key as LLM_OPENAI_API_KEY in some configurations.
    """
    # Try dedicated video key first, fallback to general OpenAI key
    video_key = os.getenv("OPENAI_VIDEO_API_KEY", "")
    if video_key:
        return video_key

    # Fallback: try using general OpenAI API key
    openai_key = os.getenv("LLM_OPENAI_API_KEY", "")
    if openai_key:
        return openai_key

    return None


def get_youtube_data_api_key() -> Optional[str]:
    """
    Returns the YouTube Data API v3 key if configured.

    Step 08: Added for trend detection and analytics

    Returns:
        API key string if YOUTUBE_DATA_API_KEY is set in .env, None otherwise

    Usage:
        Used by services/trend_source.py for YouTube trending video analysis
        Free tier: 10,000 quota units/day
        Get key at: https://console.cloud.google.com/apis/credentials
    """
    key = os.getenv("YOUTUBE_DATA_API_KEY", "")
    if not key:
        return None
    return key


def get_reddit_credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns Reddit API credentials if configured.

    Step 08 Phase 2: Added for Reddit trend detection

    Returns:
        Tuple of (client_id, client_secret, user_agent) or (None, None, None)

    Usage:
        Used by services/reddit_trend_source.py for Reddit trending posts
        Free tier: 60 requests/minute
        Get credentials at: https://www.reddit.com/prefs/apps

    Setup:
        1. Go to https://www.reddit.com/prefs/apps
        2. Click "Create App" or "Create Another App"
        3. Select "script" type
        4. Add to .env:
            REDDIT_CLIENT_ID=your_client_id
            REDDIT_CLIENT_SECRET=your_client_secret
            REDDIT_USER_AGENT=yt_autopilot:v1.0 (by /u/your_username)
    """
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent = os.getenv("REDDIT_USER_AGENT", "yt_autopilot:v1.0")

    if not client_id or not client_secret:
        return None, None, None

    return client_id, client_secret, user_agent


def get_env(key: str, default: str = "") -> str:
    """
    Generic environment variable getter.

    Args:
        key: Environment variable name
        default: Default value if key is not set

    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


# ============================================================================
# Step 08: Vertical Category Configurations
# ============================================================================

def get_vertical_configs() -> Dict[str, Dict[str, Any]]:
    """
    Returns predefined configurations for different content verticals.

    Step 08: Multi-account scaling with vertical-specific optimization

    Returns:
        Dict mapping vertical_id to VerticalConfig dict

    Usage:
        Used by trend_source.py and trend_hunter.py for vertical-aware trend selection
    """
    return {
        "tech_ai": {
            "vertical_id": "tech_ai",
            "cpm_baseline": 15.0,
            "target_keywords": [
                "AI", "ChatGPT", "Python", "automation", "productivity",
                "machine learning", "coding", "programming", "tutorial",
                "OpenAI", "Claude", "GPT", "tech news"
            ],
            "reddit_subreddits": [
                "MachineLearning", "OpenAI", "Python", "programming",
                "LocalLLaMA", "artificial", "technology", "coding"
            ],
            "youtube_category_id": "28",  # Science & Technology
            "youtube_channels": [
                {"channel_id": "UCsBjURrPoezykLs9EqgamOA", "name": "Fireship", "subscribers": "3.5M"},
                {"channel_id": "UCUyeluBRhGPCW4rPe_UvBZQ", "name": "ThePrimeagen", "subscribers": "700K"},
                {"channel_id": "UC9x0AN7BWHpCDHSm9NiJFJQ", "name": "NetworkChuck", "subscribers": "3.9M"}
            ],
            "proven_formats": {
                "tutorial": 0.35,
                "news_reaction": 0.25,
                "deep_dive": 0.20,
                "listicle": 0.20
            }
        },
        "finance": {
            "vertical_id": "finance",
            "cpm_baseline": 30.0,
            "target_keywords": [
                # Original keywords
                "finance", "investing", "money", "stocks", "crypto",
                "trading", "passive income", "budget", "real estate",
                "financial freedom", "wealth",
                # 2025 trending keywords
                "AI investing", "recession proof", "inflation hedge",
                "dividend income", "tax strategy", "side hustle",
                "compound interest", "retirement planning", "emergency fund",
                "credit score", "401k", "IRA", "debt payoff", "financial literacy"
            ],
            "reddit_subreddits": [
                # Original subreddits
                "personalfinance", "investing", "financialindependence",
                "stocks", "wallstreetbets", "CryptoCurrency",
                # Added: High-quality educational
                "Bogleheads", "fire", "StockMarket",
                # Added: Macro trends and alternative assets
                "Economics", "RealEstate", "DebtFree"
            ],
            "youtube_category_id": "25",  # News & Politics (better for finance than Howto & Style)
            "youtube_channels": [
                # Traditional finance educators (verified working channel IDs)
                {"channel_id": "UCV6KDgJskWaEckne5aPA0aQ", "name": "Graham Stephan", "subscribers": "4.22M"},
                {"channel_id": "UCGy7SkBjcIAgTiwkXEtPnYg", "name": "Andrei Jikh", "subscribers": "2.27M"},
                {"channel_id": "UCT3EznhW_CNFcfOlyDNTLLw", "name": "Minority Mindset", "subscribers": "2M"},
                {"channel_id": "UCUvvj5lwue7PspotMDjk5UA", "name": "Meet Kevin", "subscribers": "2M"},
                {"channel_id": "UCrM7B7SL_g1edFOnmj-SDKg", "name": "New Money", "subscribers": "400K"}
            ],
            "proven_formats": {
                "tutorial": 0.30,
                "news_reaction": 0.30,
                "listicle": 0.25,
                "deep_dive": 0.15
            }
        },
        "gaming": {
            "vertical_id": "gaming",
            "cpm_baseline": 8.0,
            "target_keywords": [
                "gaming", "gameplay", "esports", "stream", "twitch",
                "game review", "tips", "walkthrough", "montage"
            ],
            "reddit_subreddits": [
                "gaming", "Games", "pcgaming", "leagueoflegends",
                "valorant", "FortNiteBR"
            ],
            "youtube_category_id": "20",  # Gaming
            "youtube_channels": [],  # To be configured with gaming influencers
            "proven_formats": {
                "gameplay": 0.40,
                "tutorial": 0.25,
                "news_reaction": 0.20,
                "challenge": 0.15
            }
        },
        "education": {
            "vertical_id": "education",
            "cpm_baseline": 18.0,
            "target_keywords": [
                "tutorial", "learn", "course", "education", "study",
                "explained", "how to", "guide", "lesson"
            ],
            "reddit_subreddits": [
                "learnprogramming", "AskScience", "explainlikeimfive",
                "education", "GetStudying"
            ],
            "youtube_category_id": "27",  # Education
            "youtube_channels": [],  # To be configured with education influencers
            "proven_formats": {
                "tutorial": 0.50,
                "deep_dive": 0.30,
                "listicle": 0.20
            }
        },
        "fitness": {
            "vertical_id": "fitness",
            "cpm_baseline": 12.0,
            "target_keywords": [
                "workout", "fitness", "gym", "training", "bodybuilding",
                "muscle", "diet", "nutrition", "exercise", "weightlifting",
                "cardio", "transformation", "strength", "protein", "meal prep"
            ],
            "reddit_subreddits": [
                "fitness", "bodybuilding", "gainit", "loseit",
                "nutrition", "weightroom", "naturalbodybuilding", "leangains"
            ],
            "youtube_category_id": "17",  # Sports
            "youtube_channels": [
                {"channel_id": "UCe0TLA0EsQbE-MjuHXevj2A", "name": "ATHLEAN-X", "subscribers": "14.1M"},
                {"channel_id": "UCqjwF8rxRsotnojGl4gM0Zw", "name": "Jeff Nippard", "subscribers": "3.67M"},
                {"channel_id": "UCU0DZhN-8KFLYO6beSaYljg", "name": "FitnessFAQs", "subscribers": "2.2M"},
                {"channel_id": "UCpQ34afVgk8cRQBjSJ1xuJQ", "name": "MadFit", "subscribers": "10.6M"},
                {"channel_id": "UCEtMRF1ywKMc4sf3EXYyDzw", "name": "Scott Herman Fitness", "subscribers": "2.7M"},
                {"channel_id": "UCSswlFwBc9JSPD8fOUfK9Nw", "name": "GianzCoach", "subscribers": "435K"},
                {"channel_id": "UC58d7cLvXt9ZZq7sG7O-KRA", "name": "Andrea Presti IFBB Pro", "subscribers": "208K"}
            ],
            "proven_formats": {
                "workout_tutorial": 0.40,
                "transformation": 0.25,
                "nutrition_tips": 0.20,
                "motivational": 0.15
            }
        }
    }


def get_vertical_config(vertical_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns configuration for a specific vertical.

    Args:
        vertical_id: Vertical identifier ('tech_ai', 'finance', 'gaming', 'education')

    Returns:
        VerticalConfig dict or None if vertical_id not found
    """
    configs = get_vertical_configs()
    return configs.get(vertical_id)
