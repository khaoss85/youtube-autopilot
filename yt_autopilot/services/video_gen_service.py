"""
Video Generation Service: Generates video clips using Veo/Vertex AI (Step 06-pre)

This service connects to Google Veo (via Vertex AI) to generate short video clips
based on text prompts from the visual planner.

Integration Status (Step 06-pre):
- Veo API key reading from config ✓
- Realistic API call structure prepared ✓
- TODO: Complete binary download and save logic
- Fallback to placeholder if no API key present ✓
"""

import time
import subprocess
import requests
from pathlib import Path
from typing import List, Optional
from yt_autopilot.core.schemas import VisualPlan, VisualScene
from yt_autopilot.core.config import get_config, get_veo_api_key, get_temp_dir
from yt_autopilot.core.logger import logger


def _call_veo(prompt: str, duration_seconds: int, scene_id: int) -> str:
    """
    Calls Veo (via Vertex AI) to generate a video clip.

    Integration Readiness (Step 06-pre):
    - Reads VEO_API_KEY from config ✓
    - Prepares realistic API request structure ✓
    - TODO: Complete job polling and video download
    - Falls back to placeholder if key missing ✓

    Veo/Vertex AI Specifications:
    - Endpoint: https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/veo:generateVideo
    - Authentication: API Key or Service Account
    - Supported formats: 9:16 (vertical), 16:9 (horizontal), 1:1 (square)
    - Video length: 5-30 seconds
    - Resolution: 1080p HD
    - Response time: ~2-5 minutes per clip (async job)

    Args:
        prompt: Text description for video generation (e.g., "Modern office, camera panning")
        duration_seconds: Desired video length (5-30 seconds)
        scene_id: Scene identifier for file naming

    Returns:
        Path to generated video file (.mp4) in TEMP_DIR

    Raises:
        RuntimeError: If video generation fails
    """
    logger.info(f"Veo: Generating video for scene {scene_id}...")
    logger.debug(f"  Prompt: '{prompt[:80]}...'")
    logger.debug(f"  Duration: {duration_seconds}s")

    # Get API key from config
    api_key = get_veo_api_key()

    if not api_key:
        logger.warning("  VEO_API_KEY not found - using placeholder video")
        return _generate_placeholder_video(scene_id, prompt, duration_seconds)

    # Prepare Veo/Vertex AI request
    # TODO: Replace with actual project ID from config or service account
    project_id = "manifest-wind-465212-c5"  # From your service account
    location = "us-central1"

    endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/{location}/"
        f"publishers/google/models/veo:generateVideo"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "instances": [
            {
                "prompt": prompt,
                "videoSettings": {
                    "durationSeconds": duration_seconds,
                    "aspectRatio": "9:16",  # Vertical for Shorts
                    "quality": "1080p"
                }
            }
        ]
    }

    logger.info(f"  Calling Vertex AI Veo endpoint...")
    logger.debug(f"  Endpoint: {endpoint[:80]}...")

    try:
        # TODO (Step 06-pre): Complete this integration
        #
        # Step 1: Submit video generation job
        # response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        # response.raise_for_status()
        #
        # Step 2: Extract job ID from response
        # job_data = response.json()
        # job_id = job_data["name"]  # Format: projects/{project}/locations/{location}/operations/{operation_id}
        #
        # Step 3: Poll job until complete (Veo takes 2-5 minutes)
        # video_url = _poll_veo_job(job_id, api_key, timeout_seconds=600)
        #
        # Step 4: Download generated video to TEMP_DIR
        # temp_dir = get_temp_dir()
        # video_path = temp_dir / f"scene_{scene_id:03d}.mp4"
        # _download_video(video_url, video_path)
        #
        # Step 5: Return path
        # return str(video_path)

        # For now (Step 06-pre): Log that we WOULD call the API, but use placeholder
        logger.info("  ✓ Veo API key present - API call structure ready")
        logger.warning("  TODO: Complete job polling and download logic")
        logger.warning("  Using placeholder video for now")

        return _generate_placeholder_video(scene_id, prompt, duration_seconds)

    except requests.exceptions.RequestException as e:
        logger.error(f"  ✗ Veo API call failed: {e}")
        raise RuntimeError(f"Veo API failed for scene {scene_id}: {e}") from e


def _generate_placeholder_video(scene_id: int, prompt: str, duration_seconds: int) -> str:
    """
    Generate placeholder video file when Veo API is not available.

    This creates a REAL .mp4 video file (not a text file) using ffmpeg:
    - Black screen 1080x1920 (9:16 vertical for Shorts)
    - Silent audio track (44100Hz mono)
    - Specified duration in seconds
    - Playable with VLC/ffmpeg/any video player

    This allows the system to continue working and produce real playable videos
    even without Veo API access. The final_video.mp4 will be concatenatable by ffmpeg.

    Args:
        scene_id: Scene identifier
        prompt: Video generation prompt (logged but not used)
        duration_seconds: Requested duration

    Returns:
        Path to real .mp4 file

    Raises:
        RuntimeError: If ffmpeg fails to generate video
    """
    temp_dir = get_temp_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)

    # File path without "_PLACEHOLDER" suffix (clean naming for ffmpeg concat)
    video_path = temp_dir / f"scene_{scene_id:03d}.mp4"

    logger.info(f"  Generating placeholder video with ffmpeg...")
    logger.debug(f"    Duration: {duration_seconds}s")
    logger.debug(f"    Resolution: 1080x1920 (9:16)")
    logger.debug(f"    Output: {video_path.name}")

    # ffmpeg command to generate black video with silent audio
    # -f lavfi -i color=c=black:s=1080x1920:d=<duration> : black video source
    # -f lavfi -i anullsrc=r=44100:cl=mono : silent audio source
    # -t <duration> : duration limit
    # -pix_fmt yuv420p : compatibility with most players
    # -shortest : end when shortest input ends
    ffmpeg_cmd = [
        "ffmpeg",
        "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={duration_seconds}",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration_seconds),
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-y",  # Overwrite output file if exists
        str(video_path)
    ]

    try:
        # Run ffmpeg (suppress output with stderr=subprocess.DEVNULL)
        subprocess.run(
            ffmpeg_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Verify file was created and is not empty
        if not video_path.exists() or video_path.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg created empty or missing file: {video_path}")

        logger.info(f"  ✓ Generated placeholder: {video_path.name} ({video_path.stat().st_size} bytes)")
        return str(video_path)

    except subprocess.CalledProcessError as e:
        error_msg = f"ffmpeg failed to generate placeholder video for scene {scene_id}: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error generating placeholder video for scene {scene_id}: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e


# TODO (Future): Veo job polling
#
# def _poll_veo_job(job_id: str, api_key: str, timeout_seconds: int = 600) -> str:
#     """
#     Poll Veo video generation job until complete.
#
#     Args:
#         job_id: Job identifier from initial API call
#         api_key: Veo API key for authentication
#         timeout_seconds: Maximum time to wait (default 10 minutes)
#
#     Returns:
#         URL to download generated video
#
#     Raises:
#         TimeoutError: If job doesn't complete within timeout
#         RuntimeError: If job fails
#     """
#     pass
#
# TODO (Future): Video download
#
# def _download_video(video_url: str, output_path: Path) -> None:
#     """
#     Download generated video from URL to local file.
#
#     Args:
#         video_url: URL to video binary (from Veo job response)
#         output_path: Local path to save .mp4 file
#
#     Raises:
#         RuntimeError: If download fails
#     """
#     pass


def generate_scenes(visual_plan: VisualPlan, max_retries: int = 2) -> List[str]:
    """
    Generates all video clips for a visual plan using Veo API.

    For each scene in the visual plan:
    1. Extracts prompt and duration
    2. Calls Veo API to generate video
    3. Saves clip to temp directory
    4. Retries on failure (max 2 attempts)

    Args:
        visual_plan: Complete visual plan with scene list
        max_retries: Maximum retry attempts per scene (default: 2)

    Returns:
        List of file paths to generated video clips (.mp4)
        Ordered by scene_id

    Raises:
        RuntimeError: If any scene generation fails after all retries

    Example:
        >>> from yt_autopilot.core.schemas import VisualPlan, VisualScene
        >>> plan = VisualPlan(
        ...     aspect_ratio="9:16",
        ...     style_notes="Modern, dynamic",
        ...     scenes=[
        ...         VisualScene(
        ...             scene_id=1,
        ...             prompt_for_veo="Opening shot",
        ...             est_duration_seconds=5
        ...         )
        ...     ]
        ... )
        >>> clips = generate_scenes(plan)
        >>> print(f"Generated {len(clips)} clips")
        Generated 1 clips
    """
    logger.info("=" * 70)
    logger.info(f"VIDEO GENERATION: Starting for {len(visual_plan.scenes)} scenes")
    logger.info(f"Aspect ratio: {visual_plan.aspect_ratio}")
    logger.info(f"Style: {visual_plan.style_notes[:60]}...")
    logger.info("=" * 70)

    generated_clips: List[str] = []

    for scene in visual_plan.scenes:
        logger.info(f"\nProcessing Scene {scene.scene_id}/{len(visual_plan.scenes)}...")

        attempt = 0
        success = False
        clip_path = None

        while attempt < max_retries and not success:
            attempt += 1

            try:
                clip_path = _call_veo(
                    prompt=scene.prompt_for_veo,
                    duration_seconds=scene.est_duration_seconds,
                    scene_id=scene.scene_id
                )
                success = True

            except Exception as e:
                logger.error(f"✗ Attempt {attempt} failed for scene {scene.scene_id}: {e}")

                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s
                    logger.warning(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    error_msg = (
                        f"Failed to generate scene {scene.scene_id} "
                        f"after {max_retries} attempts"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from e

        if clip_path:
            generated_clips.append(clip_path)
            logger.info(f"✓ Scene {scene.scene_id} complete: {Path(clip_path).name}")

    logger.info("=" * 70)
    logger.info(f"VIDEO GENERATION COMPLETE: {len(generated_clips)} clips generated")
    logger.info("=" * 70)

    return generated_clips
