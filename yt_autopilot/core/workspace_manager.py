"""
Workspace Manager: Multi-account workspace management system

Enables managing multiple YouTube channels (workspaces) with different verticals,
brand identities, and configurations.

Each workspace represents a separate YouTube channel with its own:
- Vertical category (tech_ai, fitness, finance, gaming, education)
- Brand tone and visual style
- Content history and banned topics
- Performance tracking

Usage:
    from yt_autopilot.core.workspace_manager import get_active_workspace, switch_workspace

    # Get current workspace
    workspace = get_active_workspace()

    # Switch to different workspace
    switch_workspace("gym_fitness_pro")
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from yt_autopilot.core.logger import logger


# Workspace directory
WORKSPACE_DIR = Path(__file__).parent.parent.parent / "workspaces"
ACTIVE_WORKSPACE_FILE = Path(__file__).parent.parent.parent / ".active_workspace"


def _ensure_workspace_dir():
    """Ensures workspace directory exists"""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def _get_workspace_path(workspace_id: str) -> Path:
    """Returns path to workspace JSON file"""
    return WORKSPACE_DIR / f"{workspace_id}.json"


def list_workspaces() -> List[Dict[str, Any]]:
    """
    Lists all available workspaces.

    Returns:
        List of workspace info dicts with id, name, vertical

    Example:
        >>> workspaces = list_workspaces()
        >>> for ws in workspaces:
        ...     print(f"{ws['workspace_id']}: {ws['workspace_name']}")
    """
    _ensure_workspace_dir()

    workspaces = []
    for workspace_file in WORKSPACE_DIR.glob("*.json"):
        try:
            with open(workspace_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            workspaces.append({
                "workspace_id": config.get("workspace_id", workspace_file.stem),
                "workspace_name": config.get("workspace_name", "Unknown"),
                "vertical_id": config.get("vertical_id", "unknown"),
                "file_path": str(workspace_file)
            })
        except Exception as e:
            logger.warning(f"Failed to load workspace {workspace_file.name}: {e}")

    # Sort by workspace_id
    workspaces.sort(key=lambda x: x['workspace_id'])

    return workspaces


def get_active_workspace_id() -> Optional[str]:
    """
    Gets the currently active workspace ID.

    Returns:
        Workspace ID string, or None if not set
    """
    if not ACTIVE_WORKSPACE_FILE.exists():
        return None

    try:
        with open(ACTIVE_WORKSPACE_FILE, 'r') as f:
            workspace_id = f.read().strip()
        return workspace_id if workspace_id else None
    except Exception as e:
        logger.warning(f"Failed to read active workspace file: {e}")
        return None


def set_active_workspace_id(workspace_id: str):
    """
    Sets the active workspace ID.

    Args:
        workspace_id: Workspace to activate
    """
    with open(ACTIVE_WORKSPACE_FILE, 'w') as f:
        f.write(workspace_id)

    logger.info(f"Set active workspace: {workspace_id}")


def workspace_exists(workspace_id: str) -> bool:
    """
    Checks if a workspace exists.

    Args:
        workspace_id: Workspace ID to check

    Returns:
        True if workspace file exists
    """
    return _get_workspace_path(workspace_id).exists()


def load_workspace_config(workspace_id: str) -> Dict[str, Any]:
    """
    Loads complete workspace configuration.

    Args:
        workspace_id: Workspace ID to load

    Returns:
        Workspace configuration dict

    Raises:
        FileNotFoundError: If workspace doesn't exist
        ValueError: If workspace config is invalid
    """
    workspace_path = _get_workspace_path(workspace_id)

    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace '{workspace_id}' not found at {workspace_path}")

    try:
        with open(workspace_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Validate required fields
        required_fields = ["workspace_id", "workspace_name", "vertical_id", "brand_tone"]
        missing_fields = [f for f in required_fields if f not in config]

        if missing_fields:
            raise ValueError(f"Workspace '{workspace_id}' missing required fields: {missing_fields}")

        logger.debug(f"Loaded workspace: {config['workspace_name']} ({workspace_id})")
        return config

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in workspace '{workspace_id}': {e}")


def save_workspace_config(workspace_id: str, config: Dict[str, Any]):
    """
    Saves workspace configuration.

    Args:
        workspace_id: Workspace ID to save
        config: Complete workspace configuration dict
    """
    _ensure_workspace_dir()

    workspace_path = _get_workspace_path(workspace_id)

    # Ensure workspace_id matches
    config["workspace_id"] = workspace_id

    with open(workspace_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    logger.debug(f"Saved workspace: {workspace_id}")


def get_active_workspace() -> Dict[str, Any]:
    """
    Gets the active workspace configuration.

    This is the main function used by the pipeline to get current workspace.

    Returns:
        Active workspace configuration dict

    Raises:
        RuntimeError: If no active workspace is set or workspace not found

    Example:
        >>> workspace = get_active_workspace()
        >>> print(f"Working on: {workspace['workspace_name']}")
        >>> vertical_id = workspace['vertical_id']
    """
    workspace_id = get_active_workspace_id()

    if not workspace_id:
        # Try to find first available workspace
        workspaces = list_workspaces()
        if not workspaces:
            raise RuntimeError(
                "No active workspace set and no workspaces available. "
                "Please create a workspace or run: python run.py --create-workspace"
            )

        # Auto-select first workspace
        workspace_id = workspaces[0]['workspace_id']
        logger.warning(f"No active workspace set, auto-selecting: {workspace_id}")
        set_active_workspace_id(workspace_id)

    return load_workspace_config(workspace_id)


def switch_workspace(workspace_id: str) -> Dict[str, Any]:
    """
    Switches to a different workspace.

    Args:
        workspace_id: Workspace to switch to

    Returns:
        New active workspace configuration

    Raises:
        FileNotFoundError: If workspace doesn't exist
    """
    if not workspace_exists(workspace_id):
        available = [ws['workspace_id'] for ws in list_workspaces()]
        raise FileNotFoundError(
            f"Workspace '{workspace_id}' not found. Available workspaces: {', '.join(available)}"
        )

    # Load workspace to validate
    config = load_workspace_config(workspace_id)

    # Set as active
    set_active_workspace_id(workspace_id)

    logger.info(f"Switched to workspace: {config['workspace_name']} ({workspace_id})")
    logger.info(f"  Vertical: {config['vertical_id']}")
    logger.info(f"  Brand tone: {config.get('brand_tone', 'Not set')[:50]}...")

    return config


def create_workspace(
    workspace_id: str,
    workspace_name: str,
    vertical_id: str,
    brand_tone: str = "Direct, positive, educational",
    visual_style: str = "Clean, modern, high-paced",
    banned_topics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Creates a new workspace with default configuration.

    Args:
        workspace_id: Unique identifier (e.g., "gym_fitness_pro")
        workspace_name: Display name (e.g., "Gym & Fitness Pro")
        vertical_id: Vertical category (tech_ai, fitness, finance, gaming, education)
        brand_tone: Brand voice description
        visual_style: Visual style description
        banned_topics: List of topics to avoid

    Returns:
        Created workspace configuration

    Raises:
        ValueError: If workspace already exists
    """
    if workspace_exists(workspace_id):
        raise ValueError(f"Workspace '{workspace_id}' already exists")

    if banned_topics is None:
        banned_topics = []

    config = {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "vertical_id": vertical_id,
        "brand_tone": brand_tone,
        "visual_style": visual_style,
        "banned_topics": banned_topics,
        "recent_titles": []
    }

    save_workspace_config(workspace_id, config)

    logger.info(f"Created workspace: {workspace_name} ({workspace_id})")
    logger.info(f"  Vertical: {vertical_id}")

    return config


def update_workspace_recent_titles(workspace_id: str, new_title: str, max_titles: int = 20):
    """
    Adds a new title to workspace's recent titles list.

    Args:
        workspace_id: Workspace to update
        new_title: New video title to add
        max_titles: Maximum number of recent titles to keep
    """
    config = load_workspace_config(workspace_id)

    recent_titles = config.get("recent_titles", [])
    recent_titles.insert(0, new_title)  # Add to front
    recent_titles = recent_titles[:max_titles]  # Keep only max_titles

    config["recent_titles"] = recent_titles
    save_workspace_config(workspace_id, config)

    logger.debug(f"Updated recent titles for workspace '{workspace_id}' (now {len(recent_titles)} titles)")


def clear_workspace_recent_titles(workspace_id: str):
    """
    Clears all recent titles from a workspace.

    Args:
        workspace_id: Workspace to clear titles from
    """
    config = load_workspace_config(workspace_id)
    config["recent_titles"] = []
    save_workspace_config(workspace_id, config)
    logger.info(f"Cleared recent titles for workspace '{workspace_id}'")


def reset_workspace(workspace_id: str, keep_published: bool = True) -> Dict[str, int]:
    """
    Resets a workspace by clearing recent titles and deleting unpublished records.

    Args:
        workspace_id: Workspace to reset
        keep_published: If True, keeps SCHEDULED_ON_YOUTUBE records (default: True)

    Returns:
        Dict with counts: {'titles_cleared': N, 'records_deleted': N}
    """
    from yt_autopilot.io.datastore import delete_workspace_records

    # Clear recent titles
    config = load_workspace_config(workspace_id)
    titles_count = len(config.get('recent_titles', []))
    clear_workspace_recent_titles(workspace_id)

    # Delete unpublished records
    records_deleted = delete_workspace_records(workspace_id, keep_published=keep_published)

    logger.info(f"Reset workspace '{workspace_id}': cleared {titles_count} titles, deleted {records_deleted} records")

    return {
        'titles_cleared': titles_count,
        'records_deleted': records_deleted
    }


def get_workspace_info(workspace_id: str) -> str:
    """
    Gets formatted workspace information for display.

    Args:
        workspace_id: Workspace to get info for

    Returns:
        Formatted info string
    """
    try:
        config = load_workspace_config(workspace_id)

        # Import here to avoid circular dependency
        from yt_autopilot.core.config import get_vertical_config

        vertical_config = get_vertical_config(config['vertical_id'])
        cpm = vertical_config.get('cpm_baseline', 0) if vertical_config else 0

        info = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 WORKSPACE: {config['workspace_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ID: {config['workspace_id']}
 Vertical: {config['vertical_id']} (CPM: ${cpm:.1f})
 Brand Tone: {config.get('brand_tone', 'Not set')[:60]}...
 Recent Videos: {len(config.get('recent_titles', []))}
 Banned Topics: {len(config.get('banned_topics', []))}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return info.strip()

    except Exception as e:
        return f"Error loading workspace info: {e}"
