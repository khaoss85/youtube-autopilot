"""
Video Assembly Service: Combines video clips and audio using ffmpeg.

This service uses ffmpeg to concatenate video clips, mix audio tracks,
and produce the final video file ready for upload.
"""

import subprocess
from pathlib import Path
from typing import List
from yt_autopilot.core.schemas import VisualPlan, AssetPaths
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


def _build_lower_thirds_filter(narrator_config: dict, lower_thirds_config: dict) -> str:
    """
    Builds ffmpeg drawtext filter for lower thirds with narrator name.

    Step 09: Creates professional lower thirds overlay with fade in/out.

    Args:
        narrator_config: Narrator persona configuration with name
        lower_thirds_config: Lower thirds configuration from visual_brand_manual

    Returns:
        ffmpeg drawtext filter string

    Example output:
        "drawtext=text='Coach Marco':fontsize=24:fontcolor=white:x=10:y=(h-50):
         enable='between(t,1,4)':alpha='if(lt(t,1.5),(t-1)/0.5,if(gt(t,3.5),1-(t-3.5)/0.5,1))'"
    """
    narrator_name = narrator_config.get('name', 'Host')
    font_size = lower_thirds_config.get('font_size', 24)
    duration = lower_thirds_config.get('duration_seconds', 3)
    fade_duration = lower_thirds_config.get('fade_duration', 0.5)
    position = lower_thirds_config.get('position', 'bottom_left')

    # Determine position coordinates
    if position == 'bottom_left':
        x_pos = "10"
        y_pos = "(h-50)"
    elif position == 'bottom_right':
        x_pos = "(w-text_w-10)"
        y_pos = "(h-50)"
    elif position == 'top_left':
        x_pos = "10"
        y_pos = "30"
    elif position == 'top_right':
        x_pos = "(w-text_w-10)"
        y_pos = "30"
    else:
        # Default to bottom_left
        x_pos = "10"
        y_pos = "(h-50)"

    # Calculate timing
    start_time = 1.0  # Start 1 second into video
    end_time = start_time + duration
    fade_in_end = start_time + fade_duration
    fade_out_start = end_time - fade_duration

    # Build alpha expression for fade in/out
    # Alpha: 0 (transparent) to 1 (opaque)
    # Fade in: from start_time to fade_in_end
    # Full opacity: from fade_in_end to fade_out_start
    # Fade out: from fade_out_start to end_time
    alpha_expr = (
        f"'if(lt(t,{fade_in_end}),(t-{start_time})/{fade_duration},"
        f"if(gt(t,{fade_out_start}),1-(t-{fade_out_start})/{fade_duration},1))'"
    )

    # Build drawtext filter
    # Note: Escape single quotes in text by doubling them for ffmpeg
    narrator_name_escaped = narrator_name.replace("'", "''")

    filter_str = (
        f"drawtext=text='{narrator_name_escaped}':"
        f"fontsize={font_size}:"
        f"fontcolor=white:"
        f"x={x_pos}:"
        f"y={y_pos}:"
        f"enable='between(t,{start_time},{end_time})':"
        f"alpha={alpha_expr}"
    )

    return filter_str


def assemble_final_video(
    scene_paths: List[str],
    voiceover_path: str,
    visuals: VisualPlan,
    asset_paths: AssetPaths,
    workspace_config: dict = None
) -> str:
    """
    Assembles final video from scene clips and voiceover audio using ffmpeg.

    Step 07.4: Updated to use AssetPaths for organized output
    Step 09: Added lower thirds with narrator name overlay support

    Process:
    1. Create concat file listing all scene clips
    2. Concatenate clips maintaining timestamps
    3. Mix voiceover audio track
    4. Add lower thirds with narrator name if enabled (Step 09)
    5. Add intro/outro if configured
    6. Export final video optimized for YouTube Shorts

    ffmpeg command structure:
    ```bash
    ffmpeg -f concat -safe 0 -i filelist.txt \\
           -i voiceover.wav \\
           -vf "drawtext=..." \\  # Lower thirds filter (Step 09)
           -c:v libx264 -preset fast -crf 23 \\
           -c:a aac -b:a 128k \\
           -shortest \\
           output.mp4
    ```

    Args:
        scene_paths: List of paths to scene video files (.mp4)
        voiceover_path: Path to voiceover audio file (.wav)
        visuals: Visual plan for metadata and timing
        asset_paths: AssetPaths object for organized output directory
        workspace_config: Optional workspace configuration with visual_brand_manual (Step 09)

    Returns:
        Path to final assembled video (.mp4) in asset-specific directory

    Raises:
        RuntimeError: If ffmpeg is not available or assembly fails
        FileNotFoundError: If input files don't exist

    Example:
        >>> scene_paths = ["./output/vid1/scenes/scene_1.mp4", "./output/vid1/scenes/scene_2.mp4"]
        >>> voiceover = "./output/vid1/voiceover.wav"
        >>> from yt_autopilot.core.schemas import VisualPlan, VisualScene
        >>> from yt_autopilot.core.asset_manager import create_asset_paths
        >>> plan = VisualPlan(
        ...     aspect_ratio="9:16",
        ...     style_notes="Test",
        ...     scenes=[VisualScene(scene_id=1, prompt_for_veo="Test", est_duration_seconds=5)]
        ... )
        >>> paths = create_asset_paths("video_123")
        >>> final_video = assemble_final_video(scene_paths, voiceover, plan, paths)
        >>> print(f"Final video: {final_video}")
        Final video: ./output/video_123/final_video.mp4
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
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Create concat file for ffmpeg
    concat_file = temp_dir / "filelist.txt"
    with open(concat_file, "w") as f:
        for scene_path in scene_paths:
            # ffmpeg concat format requires absolute paths and specific format
            abs_path = Path(scene_path).resolve()
            f.write(f"file '{abs_path}'\n")

    logger.info(f"Created concat file: {concat_file}")

    # Step 07.4: Use asset-specific output path
    output_file = Path(asset_paths.final_video_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    # Step 09: Check if lower thirds should be added
    use_lower_thirds = False
    lower_thirds_filter = None

    if workspace_config:
        brand_manual = workspace_config.get('visual_brand_manual', {})
        narrator_config = workspace_config.get('narrator_persona', {})

        if brand_manual.get('enabled'):
            lower_thirds_config = brand_manual.get('lower_thirds', {})

            if (lower_thirds_config.get('enabled') and
                lower_thirds_config.get('display_narrator_name') and
                narrator_config.get('enabled') and
                narrator_config.get('name')):

                use_lower_thirds = True
                lower_thirds_filter = _build_lower_thirds_filter(narrator_config, lower_thirds_config)
                logger.info(f"  Adding lower thirds: '{narrator_config.get('name')}'")
                logger.info(f"  Position: {lower_thirds_config.get('position', 'bottom_left')}")
                logger.info(f"  Duration: {lower_thirds_config.get('duration_seconds', 3)}s")

    # Build ffmpeg command
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file if exists
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),  # Input: concatenated scenes
        "-i", str(voiceover_path),  # Input: voiceover audio
    ]

    # Step 09: Add video filter if lower thirds enabled
    if use_lower_thirds and lower_thirds_filter:
        ffmpeg_cmd.extend(["-vf", lower_thirds_filter])

    # Add encoding parameters
    ffmpeg_cmd.extend([
        "-c:v", "libx264",  # Video codec
        "-preset", "fast",  # Encoding speed/quality tradeoff
        "-crf", "23",  # Quality (lower = better, 18-28 range)
        "-c:a", "aac",  # Audio codec
        "-b:a", "128k",  # Audio bitrate
        "-shortest",  # End when shortest stream ends
        "-movflags", "+faststart",  # Enable streaming
        str(output_file)
    ])

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
