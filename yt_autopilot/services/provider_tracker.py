"""
Provider Tracker: Global tracking of which providers were used for content generation.

Step 07.2: Tracks creative quality provider information for audit trail.

This module provides a simple global state for services to register which
provider they used (real AI vs fallback). The pipeline can then query this
information to save in datastore for review console display.
"""

from typing import Optional
from threading import Lock


class ProviderTracker:
    """
    Thread-safe tracker for provider usage during video generation.

    Services register which provider they used, and the pipeline
    queries this information for datastore recording.
    """

    def __init__(self):
        self._lock = Lock()
        self._video_provider: Optional[str] = None
        self._voice_provider: Optional[str] = None
        self._thumb_provider: Optional[str] = None

    def reset(self) -> None:
        """Resets all tracked providers (call at start of new generation)."""
        with self._lock:
            self._video_provider = None
            self._voice_provider = None
            self._thumb_provider = None

    def set_video_provider(self, provider: str) -> None:
        """Sets video provider (OPENAI_VIDEO, VEO, FALLBACK_PLACEHOLDER)."""
        with self._lock:
            self._video_provider = provider

    def set_voice_provider(self, provider: str) -> None:
        """Sets voice provider (REAL_TTS, FALLBACK_SILENT)."""
        with self._lock:
            self._voice_provider = provider

    def set_thumb_provider(self, provider: str) -> None:
        """Sets thumbnail provider (OPENAI_IMAGE, FALLBACK_PLACEHOLDER)."""
        with self._lock:
            self._thumb_provider = provider

    def get_video_provider(self) -> Optional[str]:
        """Returns video provider used, or None if not set."""
        with self._lock:
            return self._video_provider

    def get_voice_provider(self) -> Optional[str]:
        """Returns voice provider used, or None if not set."""
        with self._lock:
            return self._voice_provider

    def get_thumb_provider(self) -> Optional[str]:
        """Returns thumbnail provider used, or None if not set."""
        with self._lock:
            return self._thumb_provider

    def get_all(self) -> dict:
        """Returns all tracked providers as a dict."""
        with self._lock:
            return {
                "video_provider": self._video_provider,
                "voice_provider": self._voice_provider,
                "thumb_provider": self._thumb_provider
            }


# Global singleton instance
_tracker = ProviderTracker()


def reset_tracking() -> None:
    """Resets all provider tracking (call at start of generation)."""
    _tracker.reset()


def set_video_provider(provider: str) -> None:
    """Records which video provider was used."""
    _tracker.set_video_provider(provider)


def set_voice_provider(provider: str) -> None:
    """Records which voice provider was used."""
    _tracker.set_voice_provider(provider)


def set_thumb_provider(provider: str) -> None:
    """Records which thumbnail provider was used."""
    _tracker.set_thumb_provider(provider)


def get_video_provider() -> Optional[str]:
    """Returns video provider used."""
    return _tracker.get_video_provider()


def get_voice_provider() -> Optional[str]:
    """Returns voice provider used."""
    return _tracker.get_voice_provider()


def get_thumb_provider() -> Optional[str]:
    """Returns thumbnail provider used."""
    return _tracker.get_thumb_provider()


def get_all_providers() -> dict:
    """Returns all tracked provider information."""
    return _tracker.get_all()
