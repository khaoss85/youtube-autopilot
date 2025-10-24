"""
Video Assembly Service: Combines video clips and audio using ffmpeg.

This service uses ffmpeg to concatenate video clips, mix audio tracks,
and produce the final video file ready for upload.
"""

import subprocess
from pathlib import Path
from typing import List
from yt_autopilot.core.schemas import VisualPlan
from yt_autopilot.core.config import get_config
from yt_autopilot.core.logger import logger


def _check_ffmpeg_available() -> bool:
    """
    Checks if ffmpeg is installed and accessible.

    Returns:
        True if ffmpeg is available, False otherwise
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def assemble_final_video(
    scene_paths: List[str],
    voiceover_path: str,
    visuals: VisualPlan
) -> str:
    """
    Assembles final video from scene clips and voiceover audio using ffmpeg.

    Process:
    1. Create concat file listing all scene clips
    2. Concatenate clips maintaining timestamps
    3. Mix voiceover audio track
    4. Add intro/outro if configured
    5. Export final video optimized for YouTube Shorts

    ffmpeg command structure:
    ```bash
    ffmpeg -f concat -safe 0 -i filelist.txt \\
           -i voiceover.wav \\
           -c:v libx264 -preset fast -crf 23 \\
           -c:a aac -b:a 128k \\
           -shortest \\
           output.mp4
    ```

    Args:
        scene_paths: List of paths to scene video files (.mp4)
        voiceover_path: Path to voiceover audio file (.wav)
        visuals: Visual plan for metadata and timing

    Returns:
        Path to final assembled video (.mp4)

    Raises:
        RuntimeError: If ffmpeg is not available or assembly fails
        FileNotFoundError: If input files don't exist

    Example:
        >>> scene_paths = ["./tmp/scene_001.mp4", "./tmp/scene_002.mp4"]
        >>> voiceover = "./tmp/voiceover.wav"
        >>> from yt_autopilot.core.schemas import VisualPlan, VisualScene
        >>> plan = VisualPlan(
        ...     aspect_ratio="9:16",
        ...     style_notes="Test",
        ...     scenes=[VisualScene(scene_id=1, prompt_for_veo="Test", est_duration_seconds=5)]
        ... )
        >>> final_video = assemble_final_video(scene_paths, voiceover, plan)
        >>> print(f"Final video: {final_video}")
        Final video: ./output/final_video.mp4
    """
    logger.info("=" * 70)
    logger.info("VIDEO ASSEMBLY: Starting ffmpeg processing")
    logger.info(f"  Input scenes: {len(scene_paths)}")
    logger.info(f"  Voiceover: {Path(voiceover_path).name}")
    logger.info(f"  Aspect ratio: {visuals.aspect_ratio}")
    logger.info("=" * 70)

    # Check ffmpeg availability
    if not _check_ffmpeg_available():
        error_msg = (
            "ffmpeg is not installed or not in PATH. "
            "Install ffmpeg: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Verify input files exist
    for scene_path in scene_paths:
        if not Path(scene_path).exists():
            raise FileNotFoundError(f"Scene file not found: {scene_path}")

    if not Path(voiceover_path).exists():
        raise FileNotFoundError(f"Voiceover file not found: {voiceover_path}")

    config = get_config()
    temp_dir = config["TEMP_DIR"]
    output_dir = config["OUTPUT_DIR"]
    temp_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create concat file for ffmpeg
    concat_file = temp_dir / "filelist.txt"
    with open(concat_file, "w") as f:
        for scene_path in scene_paths:
            # ffmpeg concat format requires absolute paths and specific format
            abs_path = Path(scene_path).resolve()
            f.write(f"file '{abs_path}'\n")

    logger.info(f"Created concat file: {concat_file}")

    # Output file path
    output_file = output_dir / "final_video.mp4"

    # Build ffmpeg command
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file if exists
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),  # Input: concatenated scenes
        "-i", str(voiceover_path),  # Input: voiceover audio
        "-c:v", "libx264",  # Video codec
        "-preset", "fast",  # Encoding speed/quality tradeoff
        "-crf", "23",  # Quality (lower = better, 18-28 range)
        "-c:a", "aac",  # Audio codec
        "-b:a", "128k",  # Audio bitrate
        "-shortest",  # End when shortest stream ends
        "-movflags", "+faststart",  # Enable streaming
        str(output_file)
    ]

    logger.info("Executing ffmpeg command...")
    logger.debug(f"Command: {' '.join(ffmpeg_cmd)}")

    try:
        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error("ffmpeg failed:")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            raise RuntimeError(f"ffmpeg failed with return code {result.returncode}")

        logger.info("✓ ffmpeg processing complete")

        # Verify output file was created
        if not output_file.exists():
            raise RuntimeError("Output video file was not created")

        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        logger.info(f"✓ Final video saved: {output_file}")
        logger.info(f"  File size: {file_size_mb:.2f} MB")

        logger.info("=" * 70)
        logger.info("VIDEO ASSEMBLY COMPLETE")
        logger.info("=" * 70)

        return str(output_file)

    except subprocess.TimeoutExpired:
        error_msg = "ffmpeg processing timed out after 5 minutes"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    except Exception as e:
        logger.error(f"Video assembly failed: {e}")
        raise
