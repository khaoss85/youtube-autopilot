"""
Reference Image Generator Service: Generate visual references for video scenes.

Phase 1 Refactor: Creates reference images using DALL-E 3 for professional
script visualization. Images help understand the visual direction before
production.
"""

import os
import requests
from pathlib import Path
from typing import Dict, Any
from yt_autopilot.core.schemas import ContentPackage
from yt_autopilot.core.config import get_config, get_llm_openai_key
from yt_autopilot.core.logger import logger


def generate_scene_reference_images(
    content_package: ContentPackage,
    script_internal_id: str,
    workspace_config: Dict[str, Any]
) -> ContentPackage:
    """
    Generates reference images for all scenes using DALL-E 3.

    Creates high-quality visual references to help understand the intended
    visual direction for each scene. Images are saved locally and paths
    are updated in the ContentPackage.

    Args:
        content_package: ContentPackage with scenes
        script_internal_id: Script identifier for output path
        workspace_config: Workspace configuration

    Returns:
        Updated ContentPackage with reference_image_path set for each scene

    Raises:
        RuntimeError: If OpenAI API key not configured or generation fails

    Example:
        >>> package = generate_scene_reference_images(package, "abc123", workspace)
        >>> # Now package.visuals.scenes[0].reference_image_path contains the image path
    """
    logger.info(f"Generating reference images for script: {script_internal_id}")

    # Check for OpenAI API key
    openai_key = get_llm_openai_key()
    if not openai_key:
        raise RuntimeError(
            "OpenAI API key not configured. Set LLM_OPENAI_API_KEY in .env file.\n"
            "Get your key at: https://platform.openai.com/api-keys"
        )

    # Setup output directory
    config = get_config()
    workspace_id = workspace_config.get("workspace_id", "default")
    output_dir = config["OUTPUT_DIR"] / workspace_id / script_internal_id / "reference_images"
    output_dir.mkdir(parents=True, exist_ok=True)

    visual_style = workspace_config.get("visual_style", "cinematic professional")

    # Generate image for each scene
    visuals = content_package.visuals
    total_scenes = len(visuals.scenes)

    for idx, scene in enumerate(visuals.scenes):
        scene_id = scene.scene_id
        logger.info(f"  Scene {scene_id}/{total_scenes-1}: Generating reference image...")

        # Create DALL-E optimized prompt
        # Convert video prompt to still image prompt
        dalle_prompt = _create_dalle_prompt(
            scene.prompt_for_ai_tool,
            scene.segment_type or "scene",
            visual_style
        )

        logger.info(f"    DALL-E prompt: {dalle_prompt[:100]}...")

        try:
            # Call DALL-E 3 API
            image_url = _generate_image_with_dalle(dalle_prompt, openai_key)

            # Download image
            image_path = output_dir / f"scene_{scene_id}.png"
            _download_image(image_url, image_path)

            # Update scene with image path
            scene.reference_image_path = str(image_path)

            logger.info(f"    ✓ Image saved: {image_path}")

        except Exception as e:
            logger.error(f"    ✗ Failed to generate image for scene {scene_id}: {e}")
            # Continue with other scenes
            continue

    logger.info(f"✓ Reference images generated: {output_dir}")
    logger.info(f"  Total scenes: {total_scenes}")
    successful = sum(1 for s in visuals.scenes if s.reference_image_path)
    logger.info(f"  Successful: {successful}/{total_scenes}")

    return content_package


def _create_dalle_prompt(video_prompt: str, segment_type: str, visual_style: str) -> str:
    """
    Converts video generation prompt to DALL-E still image prompt.

    Optimizes the prompt for single frame generation while maintaining
    the visual intent.

    Args:
        video_prompt: Original prompt for video generation
        segment_type: Type of segment (hook, context, etc.)
        visual_style: Visual style from workspace

    Returns:
        Optimized DALL-E prompt
    """
    # Remove video-specific language
    clean_prompt = video_prompt.replace("video", "image")
    clean_prompt = clean_prompt.replace("footage", "photograph")
    clean_prompt = clean_prompt.replace("clip", "shot")
    clean_prompt = clean_prompt.replace("scene", "frame")

    # Build DALL-E prompt
    dalle_prompt = (
        f"Professional {segment_type} frame: {clean_prompt}. "
        f"Style: {visual_style}. "
        f"High quality, cinematic lighting, vertical 9:16 composition, "
        f"suitable for YouTube Shorts thumbnail."
    )

    # DALL-E 3 has a 4000 character limit
    if len(dalle_prompt) > 4000:
        dalle_prompt = dalle_prompt[:3997] + "..."

    return dalle_prompt


def _generate_image_with_dalle(prompt: str, api_key: str) -> str:
    """
    Calls DALL-E 3 API to generate image.

    Args:
        prompt: DALL-E prompt
        api_key: OpenAI API key

    Returns:
        URL of generated image

    Raises:
        RuntimeError: If API call fails
    """
    url = "https://api.openai.com/v1/images/generations"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1792",  # Vertical format (closest to 9:16)
        "quality": "standard",  # or "hd" for higher quality (costs more)
        "style": "natural"  # or "vivid" for more dramatic
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if response.status_code != 200:
        error_msg = response.json().get("error", {}).get("message", "Unknown error")
        raise RuntimeError(f"DALL-E API error: {error_msg}")

    data = response.json()
    image_url = data["data"][0]["url"]

    return image_url


def _download_image(url: str, save_path: Path) -> None:
    """
    Downloads image from URL and saves to file.

    Args:
        url: Image URL
        save_path: Local path to save image

    Raises:
        RuntimeError: If download fails
    """
    response = requests.get(url, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Failed to download image: HTTP {response.status_code}")

    with open(save_path, "wb") as f:
        f.write(response.content)
