"""
Asset Manager: Organizes video assets into unique directories.

Step 07.4: Prevents overwriting by creating video-specific output directories.

Directory Structure:
    output/
      {video_id}/
        final_video.mp4
        thumbnail.png
        voiceover.mp3
        scenes/
          scene_1.mp4
          scene_2.mp4
          ...
        metadata.json

This ensures each video generation has its own isolated asset directory.
"""

import os
from pathlib import Path
from typing import Optional
from yt_autopilot.core.schemas import AssetPaths
from yt_autopilot.core.logger import logger


def create_asset_paths(video_id: str, base_output_dir: str = "output") -> AssetPaths:
    """
    Creates unique directory structure for a video's assets.

    Step 07.5: Added intro/outro paths for series format support.

    Args:
        video_id: Unique identifier for the video (typically script_internal_id)
        base_output_dir: Base output directory (default: "output")

    Returns:
        AssetPaths object with all file paths initialized

    Example:
        >>> paths = create_asset_paths("20250125_123456_gardening")
        >>> print(paths.output_dir)
        output/20250125_123456_gardening
        >>> print(paths.final_video_path)
        output/20250125_123456_gardening/final_video.mp4
    """
    # Create base output directory for this video
    output_dir = os.path.join(base_output_dir, video_id)
    scenes_dir = os.path.join(output_dir, "scenes")

    # Create directories if they don't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(scenes_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"Created asset directory structure: {output_dir}")

    # Initialize asset paths
    asset_paths = AssetPaths(
        video_id=video_id,
        output_dir=output_dir,
        final_video_path=os.path.join(output_dir, "final_video.mp4"),
        thumbnail_path=os.path.join(output_dir, "thumbnail.png"),
        voiceover_path=os.path.join(output_dir, "voiceover.mp3"),
        scene_video_paths=[],  # Will be populated as scenes are generated
        metadata_path=os.path.join(output_dir, "metadata.json"),
        intro_path=os.path.join(output_dir, "intro.mp4"),  # Step 07.5: intro video
        outro_path=os.path.join(output_dir, "outro.mp4")  # Step 07.5: outro video
    )

    return asset_paths


def get_scene_path(asset_paths: AssetPaths, scene_id: int) -> str:
    """
    Gets the file path for a specific scene video.

    Args:
        asset_paths: AssetPaths object for the video
        scene_id: Scene number (1-indexed)

    Returns:
        Full path to the scene video file

    Example:
        >>> paths = create_asset_paths("20250125_123456_gardening")
        >>> scene_path = get_scene_path(paths, 1)
        >>> print(scene_path)
        output/20250125_123456_gardening/scenes/scene_1.mp4
    """
    scenes_dir = os.path.join(asset_paths.output_dir, "scenes")
    return os.path.join(scenes_dir, f"scene_{scene_id}.mp4")


def register_scene_path(asset_paths: AssetPaths, scene_id: int, scene_path: str) -> None:
    """
    Registers a generated scene video path in the AssetPaths object.

    Args:
        asset_paths: AssetPaths object to update
        scene_id: Scene number (1-indexed)
        scene_path: Full path to the generated scene video

    Note:
        Modifies asset_paths.scene_video_paths in place.
    """
    # Ensure the list is large enough (support 0-indexed scene_id)
    while len(asset_paths.scene_video_paths) <= scene_id:
        asset_paths.scene_video_paths.append("")

    # Set the path at the correct index (scene_id is 0-indexed)
    asset_paths.scene_video_paths[scene_id] = scene_path
    logger.debug(f"Registered scene {scene_id} path: {scene_path}")


def get_temp_scene_path(video_id: str, scene_id: int, temp_dir: str = "tmp") -> str:
    """
    Gets a temporary path for a scene during generation.

    This is used for intermediate files that will be moved to final location.

    Args:
        video_id: Unique identifier for the video
        scene_id: Scene number (1-indexed)
        temp_dir: Temporary directory (default: "tmp")

    Returns:
        Full path to temporary scene file

    Example:
        >>> temp_path = get_temp_scene_path("20250125_123456_gardening", 1)
        >>> print(temp_path)
        tmp/20250125_123456_gardening_scene_1.mp4
    """
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(temp_dir, f"{video_id}_scene_{scene_id}.mp4")


def cleanup_temp_files(video_id: str, temp_dir: str = "tmp") -> None:
    """
    Cleans up temporary files for a specific video after processing.

    Args:
        video_id: Unique identifier for the video
        temp_dir: Temporary directory to clean (default: "tmp")

    Note:
        Only removes files matching the video_id pattern, not the entire temp directory.
    """
    temp_path = Path(temp_dir)
    if not temp_path.exists():
        return

    # Remove only files matching this video_id
    pattern = f"{video_id}_*"
    removed_count = 0
    for temp_file in temp_path.glob(pattern):
        if temp_file.is_file():
            temp_file.unlink()
            removed_count += 1

    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} temporary files for video {video_id}")


def delete_video_assets(video_id: str, base_output_dir: str = "output") -> bool:
    """
    Deletes all asset files for a specific video.

    Removes the entire output directory for the video, including:
    - Final video
    - Thumbnail
    - Voiceover
    - Scene videos
    - Metadata
    - Intro/outro (if present)

    Args:
        video_id: Unique identifier for the video
        base_output_dir: Base output directory (default: "output")

    Returns:
        True if directory was deleted, False if it didn't exist

    Example:
        >>> delete_video_assets("20250125_123456_gardening")
        True
    """
    import shutil

    output_dir = Path(base_output_dir) / video_id

    if not output_dir.exists():
        logger.debug(f"Asset directory does not exist: {output_dir}")
        return False

    try:
        shutil.rmtree(output_dir)
        logger.info(f"✓ Deleted asset directory: {output_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete asset directory {output_dir}: {e}")
        return False
