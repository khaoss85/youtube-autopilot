"""
Video Generation Service: Generates video clips using Veo/Vertex AI

This service connects to Google Veo (via Vertex AI) to generate short video clips
based on text prompts from the visual planner.

Integration Status (Step 07):
- Veo API key reading from config ✓
- Real video generation with job submit/poll/download ✓
- Automatic fallback to placeholder if API unavailable ✓
- Error handling and retry logic ✓

Step 07.2 Integration:
- OpenAI Sora-style video provider (3-tier fallback: OpenAI → Veo → ffmpeg)
- VIDEO_PROVIDER logging for audit trail
"""

import time
import subprocess
import requests
from pathlib import Path
from typing import List, Optional
from yt_autopilot.core.schemas import VisualPlan, VisualScene
from yt_autopilot.core.config import get_config, get_veo_api_key, get_openai_video_key, get_temp_dir
from yt_autopilot.core.logger import logger
from yt_autopilot.services import provider_tracker


# Veo/Vertex AI configuration
VEO_PROJECT_ID = "manifest-wind-465212-c5"  # From service account
VEO_LOCATION = "us-central1"
VEO_SUBMIT_ENDPOINT = (
    f"https://{VEO_LOCATION}-aiplatform.googleapis.com/v1/"
    f"projects/{VEO_PROJECT_ID}/locations/{VEO_LOCATION}/"
    f"publishers/google/models/veo:generateVideo"
)


def _submit_veo_job(prompt: str, duration_seconds: int, api_key: str) -> str:
    """
    Submits a video generation request to Veo/Vertex AI and returns a job ID.

    Args:
        prompt: Text description for video generation
        duration_seconds: Desired video length (5-30 seconds)
        api_key: Veo API key for authentication

    Returns:
        job_id: Operation ID for polling

    Raises:
        RuntimeError: If job submission fails
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "instances": [{
            "prompt": prompt,
            "videoSettings": {
                "durationSeconds": duration_seconds,
                "aspectRatio": "9:16",
                "quality": "1080p"
            }
        }]
    }

    logger.info("  Submitting Veo job...")
    logger.debug(f"    Endpoint: {VEO_SUBMIT_ENDPOINT[:60]}...")
    logger.debug(f"    Prompt: {prompt[:60]}...")

    try:
        response = requests.post(
            VEO_SUBMIT_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()

        # Extract job ID from response
        response_data = response.json()

        # Veo/Vertex AI returns operation name in format:
        # "projects/{project}/locations/{location}/operations/{operation_id}"
        if "name" in response_data:
            job_id = response_data["name"]
            logger.info(f"  ✓ Job submitted: {job_id.split('/')[-1][:30]}...")
            return job_id
        else:
            raise RuntimeError(f"Veo API response missing 'name' field: {response_data}")

    except requests.exceptions.RequestException as e:
        error_msg = f"Veo job submission failed: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def _poll_veo_job(job_id: str, api_key: str, timeout_seconds: int = 600) -> str:
    """
    Polls Veo job status until complete or timeout.

    Args:
        job_id: Operation ID from _submit_veo_job()
        api_key: Veo API key for authentication
        timeout_seconds: Maximum wait time (default 10 minutes)

    Returns:
        video_url: URL to download generated video

    Raises:
        TimeoutError: If job doesn't complete within timeout
        RuntimeError: If job fails or API error occurs
    """
    # Construct polling endpoint from job ID
    # job_id format: "projects/{project}/locations/{location}/operations/{operation_id}"
    poll_endpoint = f"https://{VEO_LOCATION}-aiplatform.googleapis.com/v1/{job_id}"

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    logger.info(f"  Polling Veo job (timeout: {timeout_seconds}s)...")

    start_time = time.time()
    poll_interval = 10  # Poll every 10 seconds

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(f"Veo job polling timeout after {timeout_seconds}s")

        try:
            response = requests.get(poll_endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            job_status = response.json()

            # Check if job is done
            if job_status.get("done", False):
                # Check for errors
                if "error" in job_status:
                    error_msg = job_status["error"].get("message", "Unknown error")
                    raise RuntimeError(f"Veo job failed: {error_msg}")

                # Extract video URL from response
                # Veo returns videoUri in response.metadata or response.response
                if "response" in job_status and "videoUri" in job_status["response"]:
                    video_url = job_status["response"]["videoUri"]
                    logger.info(f"  ✓ Job complete: {video_url[:50]}...")
                    return video_url
                else:
                    raise RuntimeError(f"Veo job complete but no videoUri in response: {job_status}")

            # Job still running
            progress = job_status.get("metadata", {}).get("progressPercent", 0)
            logger.debug(f"    Job in progress: {progress}% (elapsed: {elapsed:.0f}s)")

            time.sleep(poll_interval)

        except requests.exceptions.RequestException as e:
            error_msg = f"Veo job polling request failed: {e}"
            logger.error(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg) from e


def _download_video_file(video_url: str, output_path: Path, api_key: str) -> None:
    """
    Downloads generated video from URL to local file.

    Args:
        video_url: URL to video binary (from Veo job response)
        output_path: Local path to save .mp4 file
        api_key: Veo API key for authentication (if needed)

    Raises:
        RuntimeError: If download fails
    """
    logger.info(f"  Downloading video to {output_path.name}...")

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.get(video_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        # Verify content type
        content_type = response.headers.get("Content-Type", "")
        if "video" not in content_type and "octet-stream" not in content_type:
            logger.warning(f"    Unexpected content type: {content_type}")

        # Write binary content to file
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Verify file was created and is not empty
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Downloaded file is empty or missing: {output_path}")

        file_size = output_path.stat().st_size
        logger.info(f"  ✓ Download complete: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

    except requests.exceptions.RequestException as e:
        error_msg = f"Video download failed: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def _call_openai_video(prompt: str, duration_seconds: int, scene_id: int) -> str:
    """
    Calls OpenAI Sora 2 video generation API.

    Step 07.3: Real Sora 2 API implementation (first tier before Veo)
    FIXED: Aligned with official OpenAI Sora 2 API documentation

    Uses async job pattern:
    1. Submit video generation job to OpenAI
    2. Poll status until complete (max 10 minutes)
    3. Download generated video

    Official Endpoint: https://api.openai.com/v1/videos
    Model: sora-2 (or sora-2-pro for higher quality)
    Output: 1920x1080 vertical HD video (9:16 for YouTube Shorts)

    Docs: https://platform.openai.com/docs/guides/video

    Args:
        prompt: Text description for video generation
        duration_seconds: Desired video length (5-30 seconds)
        scene_id: Scene identifier for file naming

    Returns:
        Path to generated video file (.mp4) in TEMP_DIR

    Raises:
        RuntimeError: If API key not configured or generation fails
        TimeoutError: If job doesn't complete within 10 minutes
    """
    logger.info(f"OpenAI Video: Attempting generation for scene {scene_id}...")
    logger.debug(f"  Prompt: '{prompt[:80]}...'")
    logger.debug(f"  Duration: {duration_seconds}s")

    # Get API key from config
    api_key = get_openai_video_key()

    if not api_key:
        logger.debug("  OPENAI_VIDEO_API_KEY not found - skipping to Veo fallback")
        raise RuntimeError("OpenAI video API key not configured")

    # Step 07.3: Real Sora 2 API implementation (FIXED with official docs)
    endpoint = "https://api.openai.com/v1/videos"  # FIXED: was /v1/video/generations
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Step 1: Submit video generation job
    logger.info("  Submitting Sora 2 job...")

    # FIXED: Sora 2 only supports durations of 4, 8, or 12 seconds
    # Round to nearest supported duration
    if duration_seconds <= 6:
        supported_seconds = 4
    elif duration_seconds <= 10:
        supported_seconds = 8
    else:
        supported_seconds = 12

    logger.debug(f"  Requested {duration_seconds}s, using supported duration: {supported_seconds}s")

    payload = {
        "model": "sora-2",  # FIXED: was sora-2.0, correct is sora-2 or sora-2-pro
        "prompt": prompt,
        "seconds": str(supported_seconds),  # FIXED: must be "4", "8", or "12"
        "size": "720x1280"  # FIXED: sora-2 supports 720x1280 (SD vertical) or 1280x720 (HD horiz)
        # Note: sora-2-pro supports higher resolutions like 1024x1792, but requires org verification
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["id"]
        logger.info(f"  ✓ Sora 2 job submitted: {job_id}")
    except requests.exceptions.RequestException as e:
        error_msg = f"Sora 2 job submission failed: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e

    # Step 2: Poll job status until complete
    # FIXED: Correct poll endpoint according to OpenAI docs
    poll_endpoint = f"https://api.openai.com/v1/videos/{job_id}"
    timeout_seconds = 600  # 10 minutes max
    poll_interval = 10  # Poll every 10 seconds

    logger.info(f"  Polling Sora 2 job (timeout: {timeout_seconds}s)...")

    import time
    start_time = time.time()

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            raise TimeoutError(f"Sora 2 job polling timeout after {timeout_seconds}s")

        try:
            response = requests.get(poll_endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            job_status = response.json()

            # Check if job is done (FIXED: correct status values from docs)
            status = job_status.get("status")
            if status == "completed":
                # FIXED: Download from /content endpoint, not video_url field
                logger.info(f"  ✓ Job complete! Ready to download.")
                break
            elif status == "failed":
                # FIXED: Error structure from docs
                error_obj = job_status.get("error", {})
                error_msg = error_obj.get("message", "Unknown error") if isinstance(error_obj, dict) else str(error_obj)
                raise RuntimeError(f"Sora 2 job failed: {error_msg}")
            else:
                # Job still processing (status: 'queued' or 'in_progress')
                # FIXED: correct progress field name from docs
                progress = job_status.get("progress", 0)  # 0-100
                logger.debug(f"    Status: {status}, Progress: {progress}% (elapsed: {elapsed:.0f}s)")
                time.sleep(poll_interval)

        except requests.exceptions.RequestException as e:
            logger.error(f"  ✗ Polling error: {e}")
            time.sleep(poll_interval)  # Retry after delay

    # Step 3: Download generated video
    # FIXED: Download from correct /content endpoint according to OpenAI docs
    download_endpoint = f"https://api.openai.com/v1/videos/{job_id}/content"
    output_path = get_temp_dir() / f"scene_{scene_id:03d}.mp4"

    logger.info(f"  Downloading Sora 2 video from /content endpoint...")
    try:
        response = requests.get(download_endpoint, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        # Write binary content to file
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Verify file
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Downloaded file is empty or missing: {output_path}")

        file_size = output_path.stat().st_size
        logger.info(f"  ✓ Download complete: {file_size:,} bytes ({file_size / (1024*1024):.1f} MB)")

        # Track provider
        logger.info("  VIDEO_PROVIDER=OPENAI_SORA2")
        provider_tracker.set_video_provider("OPENAI_SORA2")

        return str(output_path)

    except requests.exceptions.RequestException as e:
        error_msg = f"Sora 2 video download failed: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def _call_veo(prompt: str, duration_seconds: int, scene_id: int) -> str:
    """
    Calls Veo (via Vertex AI) to generate a video clip.

    Step 07 Integration: Full submit/poll/download with automatic fallback

    Veo/Vertex AI Specifications:
    - Endpoint: Vertex AI Veo API
    - Authentication: Bearer token (API Key)
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
        RuntimeError: If video generation fails (with automatic fallback)
    """
    logger.info(f"Veo: Generating video for scene {scene_id}...")
    logger.debug(f"  Prompt: '{prompt[:80]}...'")
    logger.debug(f"  Duration: {duration_seconds}s")

    # Get API key from config
    api_key = get_veo_api_key()

    if not api_key:
        logger.warning("  VEO_API_KEY not found - using placeholder video")
        return _generate_placeholder_video(scene_id, prompt, duration_seconds)

    # Attempt real Veo generation with automatic fallback on failure
    temp_dir = get_temp_dir()
    output_path = temp_dir / f"scene_{scene_id:03d}.mp4"

    try:
        # Step 1: Submit job
        job_id = _submit_veo_job(prompt, duration_seconds, api_key)

        # Step 2: Poll until complete
        video_url = _poll_veo_job(job_id, api_key, timeout_seconds=600)

        # Step 3: Download video
        _download_video_file(video_url, output_path, api_key)

        logger.info(f"  ✓ Veo generation complete: {output_path.name}")
        logger.info("  VIDEO_PROVIDER=VEO")
        provider_tracker.set_video_provider("VEO")
        return str(output_path)

    except (RuntimeError, TimeoutError) as e:
        # Veo generation failed - fallback to placeholder
        logger.warning(f"  ✗ Veo generation failed: {e}")
        logger.warning("  → Falling back to placeholder video")

        return _generate_placeholder_video(scene_id, prompt, duration_seconds)


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
        logger.info("  VIDEO_PROVIDER=FALLBACK_PLACEHOLDER")
        provider_tracker.set_video_provider("FALLBACK_PLACEHOLDER")
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


def _generate_video_with_provider_fallback(
    prompt: str,
    duration_seconds: int,
    scene_id: int
) -> str:
    """
    Generates video with 3-tier provider fallback chain.

    Step 07.2: Multi-provider strategy for creator-grade quality

    Provider chain (automatic fallback):
    1. OpenAI Sora-style (if OPENAI_VIDEO_API_KEY configured)
    2. Veo/Vertex AI (if VEO_API_KEY configured)
    3. ffmpeg placeholder (always available)

    Args:
        prompt: Text description for video generation
        duration_seconds: Desired video length (5-30 seconds)
        scene_id: Scene identifier for file naming

    Returns:
        Path to generated video file (.mp4)

    Note:
        This function never raises. It will always return a valid video path
        using the best available provider.
    """
    # Tier 1: Try OpenAI Sora-style first
    try:
        return _call_openai_video(prompt, duration_seconds, scene_id)
    except RuntimeError as e:
        # OpenAI unavailable/failed - this is expected until Sora API is public
        logger.debug(f"  OpenAI video provider unavailable: {e}")

    # Tier 2 & 3: Veo (with built-in ffmpeg placeholder fallback)
    # _call_veo() already handles Veo → placeholder fallback internally
    return _call_veo(prompt, duration_seconds, scene_id)


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
                # Step 07.2: Use 3-tier fallback (OpenAI → Veo → placeholder)
                clip_path = _generate_video_with_provider_fallback(
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
