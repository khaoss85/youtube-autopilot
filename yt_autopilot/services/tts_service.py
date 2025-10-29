"""
Text-to-Speech Service: Converts script text to audio narration.

This service uses TTS providers (Google Cloud TTS, Amazon Polly, ElevenLabs, etc.)
to generate voiceover audio from video scripts.

Step 07 Integration: Real TTS with automatic fallback to silent audio
Step 07.2 Integration: Creator-grade Italian voice with energetic, natural tone
Step 07.3 Integration: Scene-aware generation with timing metadata for sync
Step 10 Integration: Per-scene audio generation for perfect sync alignment
"""

import os
import subprocess
import requests
from pathlib import Path
from yt_autopilot.core.schemas import VideoScript, AssetPaths
from yt_autopilot.core.config import get_config
from yt_autopilot.core.logger import logger
from yt_autopilot.services import provider_tracker


def _call_tts_provider(text: str, voice_id: str = "alloy", speed: float = 1.05) -> bytes:
    """
    Calls TTS provider API to generate speech audio.

    Currently supports OpenAI TTS API. Can be extended for ElevenLabs, Google TTS, etc.

    Step 07.2: Uses tts-1-hd model for creator-grade quality and speed parameter
    for energetic delivery.
    Step 09: Workspace-configurable voice and speed for brand consistency

    NOTE: OpenAI TTS does NOT have explicit Italian-only voices or style parameters.
    Language is auto-detected from input text. For true Italian creator voice,
    consider future integration with ElevenLabs (custom voice cloning) or Google Cloud TTS
    (it-IT voices with WaveNet quality).

    Args:
        text: Text to convert to speech
        voice_id: Voice identifier (default: "alloy" for OpenAI TTS)
                  Options: alloy, echo, fable, onyx, nova, shimmer
        speed: Playback speed (0.25-4.0, default: 1.05 for slight energy boost)

    Returns:
        Audio bytes (MP3 or WAV format)

    Raises:
        RuntimeError: If TTS API call fails or no API key configured
    """
    # Try OpenAI TTS API first
    tts_api_key = os.getenv("TTS_API_KEY", "")
    openai_key = os.getenv("LLM_OPENAI_API_KEY", "")

    api_key = tts_api_key or openai_key

    if not api_key:
        raise RuntimeError("No TTS_API_KEY or LLM_OPENAI_API_KEY found in environment")

    logger.info("  Calling OpenAI TTS API...")
    logger.debug(f"    Voice: {voice_id}")
    logger.debug(f"    Speed: {speed}")
    logger.debug(f"    Text length: {len(text)} characters")

    # OpenAI TTS API endpoint
    endpoint = "https://api.openai.com/v1/audio/speech"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Step 07.2/09: Use high-quality model with workspace-configurable voice and speed
    payload = {
        "model": "tts-1-hd",  # High-quality model for creator content
        "input": text,
        "voice": voice_id,    # Workspace-configurable (Step 09)
        "speed": speed,       # Workspace-configurable (Step 09)
        "response_format": "mp3"
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()

        # Return audio bytes
        audio_bytes = response.content

        if not audio_bytes or len(audio_bytes) < 1024:
            raise RuntimeError(f"TTS API returned insufficient audio data: {len(audio_bytes)} bytes")

        logger.info(f"  ✓ TTS generation complete: {len(audio_bytes):,} bytes")
        logger.info("  VOICE_PROVIDER=REAL_TTS")
        provider_tracker.set_voice_provider("REAL_TTS")
        return audio_bytes

    except requests.exceptions.RequestException as e:
        error_msg = f"TTS API call failed: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def synthesize_voiceover(
    script: VideoScript,
    asset_paths: AssetPaths,
    voice_id: str = "alloy",
    workspace_config: dict = None
) -> str:
    """
    Converts script text to speech audio file.

    Step 07: Real TTS integration with automatic fallback
    Step 07.3: Scene-aware generation with timing diagnostics
    Step 07.4: Updated to use AssetPaths for organized output
    Step 09: Workspace-specific voice configuration for brand consistency

    Tries to use real TTS provider (OpenAI TTS, ElevenLabs, Google Cloud TTS, etc.)
    Falls back to silent WAV if TTS unavailable or fails.

    Current implementation generates a single audio file from full_voiceover_text.
    Scene timing is handled downstream during video assembly using scene_voiceover_map.

    Future enhancement: Optional per-scene audio generation for maximum sync precision.

    Args:
        script: Video script with full voiceover text and scene_voiceover_map
        asset_paths: AssetPaths object for organized output directory
        voice_id: TTS voice identifier (default: "alloy" for OpenAI)
                  NOTE: Overridden by workspace_config.voice_config if provided
        workspace_config: Optional workspace configuration dict with voice_config
                          (Step 09: enables voice model + speed from workspace)

    Returns:
        Path to generated audio file (.wav or .mp3) in asset-specific directory

    Example:
        >>> from yt_autopilot.core.schemas import VideoScript, SceneVoiceover
        >>> from yt_autopilot.core.asset_manager import create_asset_paths
        >>> script = VideoScript(
        ...     hook="Test hook",
        ...     bullets=["Point 1"],
        ...     outro_cta="Subscribe!",
        ...     full_voiceover_text="This is a test.",
        ...     scene_voiceover_map=[
        ...         SceneVoiceover(scene_id=1, voiceover_text="Test hook", est_duration_seconds=3),
        ...         SceneVoiceover(scene_id=2, voiceover_text="Subscribe!", est_duration_seconds=2)
        ...     ]
        ... )
        >>> paths = create_asset_paths("video_123")
        >>> audio_path = synthesize_voiceover(script, paths)
        >>> print(f"Audio saved to: {audio_path}")
        Audio saved to: output/video_123/voiceover.mp3
    """
    # Step 09: Extract voice configuration from workspace if provided
    if workspace_config:
        voice_config = workspace_config.get('voice_config', {})
        configured_voice = voice_config.get('voice_model', voice_id)
        configured_speed = voice_config.get('speed', 1.05)

        logger.info("Synthesizing voiceover audio (workspace-configured)...")
        logger.info(f"  Workspace voice config:")
        logger.info(f"    Voice model: {configured_voice}")
        logger.info(f"    Speed: {configured_speed}")
        logger.info(f"  Text length: {len(script.full_voiceover_text)} characters")

        # Use workspace voice config
        voice_id = configured_voice
        speed = configured_speed
    else:
        # Legacy mode: use default parameters
        logger.info("Synthesizing voiceover audio (default config)...")
        logger.info(f"  Voice ID: {voice_id}")
        logger.info(f"  Text length: {len(script.full_voiceover_text)} characters")
        speed = 1.05  # Default speed

    # Step 07.3: Log scene-level timing information for diagnostics
    if script.scene_voiceover_map and len(script.scene_voiceover_map) > 0:
        scene_count = len(script.scene_voiceover_map)
        total_scene_duration = sum(s.est_duration_seconds for s in script.scene_voiceover_map)
        logger.info(f"  Scene-aware mode: {scene_count} scenes, ~{total_scene_duration}s total")
        logger.debug("  Scene timing breakdown:")
        for scene in script.scene_voiceover_map:
            text_preview = scene.voiceover_text[:60] + "..." if len(scene.voiceover_text) > 60 else scene.voiceover_text
            logger.debug(f"    Scene {scene.scene_id}: {scene.est_duration_seconds}s - \"{text_preview}\"")
    else:
        logger.warning("  Scene voiceover map not available - using legacy mode")
        logger.warning("  Consider regenerating script with Step 07.3+ for better sync")

    # Estimate duration from text length
    # Rule: ~150 words/minute ≈ 2.5 words/second
    word_count = len(script.full_voiceover_text.split())
    estimated_duration_sec = max(5, round(word_count / 2.5))  # Minimum 5 seconds

    logger.info(f"  Estimated duration: {estimated_duration_sec}s ({word_count} words)")

    # Try real TTS provider first
    try:
        audio_bytes = _call_tts_provider(script.full_voiceover_text, voice_id, speed)

        # Step 07.4: Save audio to asset-specific directory
        audio_path = Path(asset_paths.voiceover_path)
        audio_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        audio_path.write_bytes(audio_bytes)

        logger.info(f"✓ Real TTS voiceover generated: {audio_path.name}")
        logger.info(f"  File path: {audio_path}")
        logger.info(f"  File size: {len(audio_bytes):,} bytes ({len(audio_bytes) / 1024:.1f} KB)")

        return str(audio_path)

    except RuntimeError as e:
        # TTS failed - fallback to silent WAV
        logger.warning(f"  TTS provider unavailable or failed: {e}")
        logger.warning("  → Falling back to silent WAV placeholder")
        logger.info("  VOICE_PROVIDER=FALLBACK_SILENT")
        provider_tracker.set_voice_provider("FALLBACK_SILENT")

        # Step 07.4: Use asset-specific path (change extension to .wav for silent)
        audio_path = Path(str(asset_paths.voiceover_path).replace(".mp3", ".wav"))
        audio_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

        logger.info(f"  Generating silent WAV with ffmpeg...")
        logger.debug(f"  Output: {audio_path}")

        # Generate silent audio WAV file with ffmpeg
        ffmpeg_cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(estimated_duration_sec),
            "-acodec", "pcm_s16le",
            "-y",  # Overwrite if exists
            str(audio_path)
        ]

        try:
            # Run ffmpeg (suppress output)
            subprocess.run(
                ffmpeg_cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Verify file was created and is not empty
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                raise RuntimeError(f"ffmpeg created empty or missing WAV file: {audio_path}")

            logger.info(f"✓ Generated silent voiceover fallback: {audio_path.name}")
            logger.info(f"  File size: {audio_path.stat().st_size} bytes")
            logger.info(f"  Duration: {estimated_duration_sec}s (silent placeholder)")

            return str(audio_path)

        except subprocess.CalledProcessError as e:
            error_msg = f"ffmpeg failed to generate silent voiceover: {e}"
            logger.error(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error generating silent voiceover: {e}"
            logger.error(f"  ✗ {error_msg}")
            raise RuntimeError(error_msg) from e


def synthesize_voiceover_per_scene(
    script: VideoScript,
    asset_paths: AssetPaths,
    voice_id: str = "alloy",
    workspace_config: dict = None
) -> list[str]:
    """
    Converts script text to per-scene speech audio files for precise synchronization.

    Step 10: Per-scene audio generation for perfect video-audio sync alignment.

    This function generates a separate audio file for each scene in the script,
    allowing perfect synchronization during video assembly. Each scene's audio
    is timed precisely to match its visual duration.

    Args:
        script: Video script with scene_voiceover_map
        asset_paths: AssetPaths object for organized output directory
        voice_id: TTS voice identifier (default: "alloy" for OpenAI)
                  NOTE: Overridden by workspace_config.voice_config if provided
        workspace_config: Optional workspace configuration dict with voice_config

    Returns:
        List of paths to generated audio files (one per scene) in order

    Raises:
        RuntimeError: If TTS API call fails or scene_voiceover_map is missing

    Example:
        >>> audio_paths = synthesize_voiceover_per_scene(script, paths, workspace_config=config)
        >>> print(f"Generated {len(audio_paths)} scene audio files")
        Generated 4 scene audio files
    """
    # Validate scene_voiceover_map exists
    if not script.scene_voiceover_map or len(script.scene_voiceover_map) == 0:
        raise RuntimeError("Cannot generate per-scene audio: script.scene_voiceover_map is empty")

    # Step 09: Extract voice configuration from workspace if provided
    if workspace_config:
        voice_config = workspace_config.get('voice_config', {})
        configured_voice = voice_config.get('voice_model', voice_id)
        configured_speed = voice_config.get('speed', 1.05)

        logger.info("Synthesizing per-scene voiceover audio (workspace-configured)...")
        logger.info(f"  Workspace voice config:")
        logger.info(f"    Voice model: {configured_voice}")
        logger.info(f"    Speed: {configured_speed}")

        # Use workspace voice config
        voice_id = configured_voice
        speed = configured_speed
    else:
        # Legacy mode: use default parameters
        logger.info("Synthesizing per-scene voiceover audio (default config)...")
        logger.info(f"  Voice ID: {voice_id}")
        speed = 1.05  # Default speed

    scene_count = len(script.scene_voiceover_map)
    total_scene_duration = sum(s.est_duration_seconds for s in script.scene_voiceover_map)
    logger.info(f"  Scene count: {scene_count}")
    logger.info(f"  Total estimated duration: {total_scene_duration}s")

    audio_paths = []

    # Generate audio for each scene
    for idx, scene in enumerate(script.scene_voiceover_map, start=1):
        scene_id = scene.scene_id
        scene_text = scene.voiceover_text

        text_preview = scene_text[:60] + "..." if len(scene_text) > 60 else scene_text
        logger.info(f"  Scene {idx}/{scene_count} (ID: {scene_id}): {scene.est_duration_seconds}s")
        logger.debug(f"    Text: \"{text_preview}\"")

        try:
            # Call TTS provider for this scene
            audio_bytes = _call_tts_provider(scene_text, voice_id, speed)

            # Generate scene-specific filename
            # Format: voiceover_scene_001.mp3, voiceover_scene_002.mp3, etc.
            base_path = Path(asset_paths.voiceover_path)
            scene_audio_filename = f"{base_path.stem}_scene_{scene_id:03d}{base_path.suffix}"
            scene_audio_path = base_path.parent / scene_audio_filename

            # Ensure directory exists and save audio
            scene_audio_path.parent.mkdir(parents=True, exist_ok=True)
            scene_audio_path.write_bytes(audio_bytes)

            logger.info(f"    ✓ Scene audio generated: {scene_audio_filename}")
            logger.debug(f"      File size: {len(audio_bytes):,} bytes ({len(audio_bytes) / 1024:.1f} KB)")

            audio_paths.append(str(scene_audio_path))

        except RuntimeError as e:
            error_msg = f"Failed to generate audio for scene {scene_id}: {e}"
            logger.error(f"    ✗ {error_msg}")
            raise RuntimeError(error_msg) from e

    logger.info(f"✓ Per-scene TTS voiceover generation complete")
    logger.info(f"  Generated {len(audio_paths)} audio files")
    logger.info(f"  Total size: {sum(Path(p).stat().st_size for p in audio_paths):,} bytes")

    return audio_paths
