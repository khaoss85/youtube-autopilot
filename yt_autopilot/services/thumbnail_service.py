"""
Thumbnail Generation Service: Creates eye-catching thumbnail images.

This service generates thumbnail images based on text descriptions,
optimized for YouTube Shorts vertical format (9:16).

Step 07.2 Integration:
- OpenAI DALL-E style thumbnail generation
- Automatic fallback to PIL/text placeholder
- THUMB_PROVIDER logging for audit trail
"""

import os
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from yt_autopilot.core.schemas import PublishingPackage
from yt_autopilot.core.config import get_config, get_llm_openai_key
from yt_autopilot.core.logger import logger
from yt_autopilot.services import provider_tracker


def _call_openai_image(prompt: str, output_path: Path) -> None:
    """
    Calls OpenAI DALL-E API to generate thumbnail image.

    Step 07.2: Real AI thumbnail generation with DALL-E

    Args:
        prompt: Text description for thumbnail (e.g., "YouTube thumbnail: Bold text SHOCKING")
        output_path: Path where to save the generated PNG image

    Raises:
        RuntimeError: If API call fails or no API key configured
    """
    logger.info("  Calling OpenAI Image API (DALL-E)...")

    # Get API key
    api_key = get_llm_openai_key()

    if not api_key:
        raise RuntimeError("No LLM_OPENAI_API_KEY found in environment")

    # OpenAI Image API endpoint
    endpoint = "https://api.openai.com/v1/images/generations"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Enhanced prompt for creator-grade YouTube thumbnail
    enhanced_prompt = (
        f"Professional YouTube Shorts thumbnail, vertical 9:16 format, "
        f"scroll-stopping visual, bold colors, high contrast, eye-catching: {prompt}"
    )

    payload = {
        "model": "dall-e-3",
        "prompt": enhanced_prompt,
        "size": "1024x1792",  # Closest to 9:16 vertical (1080x1920)
        "quality": "hd",  # High quality for creator content
        "n": 1
    }

    logger.debug(f"    Prompt: {prompt[:60]}...")
    logger.debug(f"    Size: 1024x1792 (9:16 vertical)")

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        # Extract image URL from response
        response_data = response.json()

        if "data" not in response_data or len(response_data["data"]) == 0:
            raise RuntimeError(f"OpenAI Image API returned no images: {response_data}")

        image_url = response_data["data"][0]["url"]

        logger.info(f"  Downloading generated image...")

        # Download image
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()

        # Save to file
        output_path.write_bytes(img_response.content)

        # Verify file
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Downloaded image is empty or missing: {output_path}")

        logger.info(f"  ✓ AI thumbnail generated: {output_path.stat().st_size:,} bytes")
        logger.info("  THUMB_PROVIDER=OPENAI_IMAGE")
        provider_tracker.set_thumb_provider("OPENAI_IMAGE")

    except requests.exceptions.RequestException as e:
        error_msg = f"OpenAI Image API call failed: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def _generate_placeholder_thumbnail(title: str, concept: str, output_path: Path) -> None:
    """
    Generates placeholder thumbnail using PIL when AI generation unavailable.

    Creates a simple vertical 1080x1920 image with text overlay.

    Args:
        title: Video title
        concept: Thumbnail concept description
        output_path: Path where to save the generated PNG image
    """
    logger.info("  Generating placeholder thumbnail with PIL...")

    # Create vertical 9:16 image (1080x1920)
    width, height = 1080, 1920
    img = Image.new('RGB', (width, height), color=(20, 20, 30))  # Dark background

    draw = ImageDraw.Draw(img)

    # Try to use default font (no external font file needed)
    try:
        # Use larger size for readable text
        font_large = ImageFont.load_default()
    except Exception:
        font_large = None

    # Draw title text (centered)
    title_text = title[:50]  # Truncate if too long
    text_color = (255, 255, 255)

    # Simple centered text
    # For PIL without font files, use basic draw.text
    text_position = (width // 2, height // 2)

    # Draw text with outline for visibility
    draw.text(
        (width // 2 - 200, height // 2 - 50),
        title_text,
        fill=text_color,
        font=font_large
    )

    # Add "PLACEHOLDER" watermark
    draw.text(
        (width // 2 - 150, height - 100),
        "PLACEHOLDER THUMBNAIL",
        fill=(128, 128, 128),
        font=font_large
    )

    # Save as PNG
    img.save(output_path, "PNG")

    logger.info(f"  ✓ Generated placeholder thumbnail: {output_path.stat().st_size:,} bytes")
    logger.info("  THUMB_PROVIDER=FALLBACK_PLACEHOLDER")
    provider_tracker.set_thumb_provider("FALLBACK_PLACEHOLDER")


def generate_thumbnail(publishing: PublishingPackage) -> str:
    """
    Generates thumbnail image from concept description.

    Step 07.2: Real AI thumbnail generation with automatic fallback

    Provider chain:
    1. OpenAI DALL-E 3 (if LLM_OPENAI_API_KEY configured)
    2. PIL placeholder (always available)

    Thumbnail specifications for YouTube Shorts:
    - Recommended size: 1080x1920 (9:16 vertical)
    - Format: PNG
    - Max file size: 2MB
    - High contrast text for mobile viewing
    - Bold, scroll-stopping visuals

    Args:
        publishing: Publishing package with thumbnail_concept

    Returns:
        Path to generated thumbnail image (.png)

    Example:
        >>> from yt_autopilot.core.schemas import PublishingPackage
        >>> pkg = PublishingPackage(
        ...     final_title="Amazing Video",
        ...     description="Test",
        ...     tags=["test"],
        ...     thumbnail_concept="Bold text: 'AMAZING' with surprised face"
        ... )
        >>> thumb_path = generate_thumbnail(pkg)
        >>> print(f"Thumbnail saved to: {thumb_path}")
        Thumbnail saved to: ./output/thumbnail.png
    """
    logger.info("Generating thumbnail image...")
    logger.info(f"  Concept: '{publishing.thumbnail_concept[:80]}...'")

    config = get_config()
    output_dir = config["OUTPUT_DIR"]
    output_dir.mkdir(parents=True, exist_ok=True)

    thumbnail_path = output_dir / "thumbnail.png"

    # Try OpenAI Image API first
    try:
        _call_openai_image(publishing.thumbnail_concept, thumbnail_path)
        logger.info(f"✓ AI-generated thumbnail saved: {thumbnail_path}")
        return str(thumbnail_path)

    except RuntimeError as e:
        # OpenAI Image API unavailable/failed - fallback to PIL placeholder
        logger.warning(f"  OpenAI Image API unavailable: {e}")
        logger.warning("  → Falling back to PIL placeholder thumbnail")

        _generate_placeholder_thumbnail(
            publishing.final_title,
            publishing.thumbnail_concept,
            thumbnail_path
        )

        logger.info(f"✓ Placeholder thumbnail saved: {thumbnail_path}")
        return str(thumbnail_path)
