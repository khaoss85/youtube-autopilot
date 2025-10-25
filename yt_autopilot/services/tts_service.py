"""
Text-to-Speech Service: Converts script text to audio narration.

This service uses TTS providers (Google Cloud TTS, Amazon Polly, ElevenLabs, etc.)
to generate voiceover audio from video scripts.

Step 07 Integration: Real TTS with automatic fallback to silent audio
"""

import os
import subprocess
import requests
from pathlib import Path
from yt_autopilot.core.schemas import VideoScript
from yt_autopilot.core.config import get_config
from yt_autopilot.core.logger import logger


def _call_tts_provider(text: str, voice_id: str = "alloy") -> bytes:
    """
    Calls TTS provider API to generate speech audio.

    Currently supports OpenAI TTS API. Can be extended for ElevenLabs, Google TTS, etc.

    Args:
        text: Text to convert to speech
        voice_id: Voice identifier (default: "alloy" for OpenAI TTS)

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
    logger.debug(f"    Text length: {len(text)} characters")

    # OpenAI TTS API endpoint
    endpoint = "https://api.openai.com/v1/audio/speech"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "tts-1",  # or "tts-1-hd" for higher quality
        "input": text,
        "voice": voice_id,
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
        return audio_bytes

    except requests.exceptions.RequestException as e:
        error_msg = f"TTS API call failed: {e}"
        logger.error(f"  ✗ {error_msg}")
        raise RuntimeError(error_msg) from e


def synthesize_voiceover(script: VideoScript, voice_id: str = "alloy") -> str:
    """
    Converts script text to speech audio file.

    Step 07: Real TTS integration with automatic fallback

    Tries to use real TTS provider (OpenAI TTS, ElevenLabs, Google Cloud TTS, etc.)
    Falls back to silent WAV if TTS unavailable or fails.

    Args:
        script: Video script with full voiceover text
        voice_id: TTS voice identifier (default: "alloy" for OpenAI)

    Returns:
        Path to generated audio file (.wav or .mp3)

    Example:
        >>> from yt_autopilot.core.schemas import VideoScript
        >>> script = VideoScript(
        ...     hook="Test hook",
        ...     bullets=["Point 1"],
        ...     outro_cta="Subscribe!",
        ...     full_voiceover_text="This is a test."
        ... )
        >>> audio_path = synthesize_voiceover(script)
        >>> print(f"Audio saved to: {audio_path}")
        Audio saved to: ./tmp/voiceover.mp3
    """
    logger.info("Synthesizing voiceover audio...")
    logger.info(f"  Text length: {len(script.full_voiceover_text)} characters")
    logger.info(f"  Voice ID: {voice_id}")

    config = get_config()
    temp_dir = config["TEMP_DIR"]
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Estimate duration from text length
    # Rule: ~150 words/minute ≈ 2.5 words/second
    word_count = len(script.full_voiceover_text.split())
    estimated_duration_sec = max(5, round(word_count / 2.5))  # Minimum 5 seconds

    logger.info(f"  Estimated duration: {estimated_duration_sec}s ({word_count} words)")

    # Try real TTS provider first
    try:
        audio_bytes = _call_tts_provider(script.full_voiceover_text, voice_id)

        # Save audio bytes to file (MP3 format from OpenAI TTS)
        audio_path = temp_dir / "voiceover.mp3"
        audio_path.write_bytes(audio_bytes)

        logger.info(f"✓ Real TTS voiceover generated: {audio_path.name}")
        logger.info(f"  File size: {len(audio_bytes):,} bytes ({len(audio_bytes) / 1024:.1f} KB)")

        return str(audio_path)

    except RuntimeError as e:
        # TTS failed - fallback to silent WAV
        logger.warning(f"  TTS provider unavailable or failed: {e}")
        logger.warning("  → Falling back to silent WAV placeholder")

        audio_path = temp_dir / "voiceover.wav"

        logger.info(f"  Generating silent WAV with ffmpeg...")

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
