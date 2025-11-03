"""
Semantic Similarity Utility

Provides semantic text similarity computation using sentence-transformers.
Used for semantic CTA matching (FASE 3) to reduce false positives from paraphrasing.

Key Features:
- Replaces character-based similarity (SequenceMatcher)
- Uses sentence-transformers (all-MiniLM-L6-v2, 80MB model)
- Cached model loading for performance
- Cosine similarity for semantic matching

Author: YT Autopilot Team
Version: 1.0 (FASE 3 - Semantic CTA Validation)
"""

from typing import Optional
from functools import lru_cache
from yt_autopilot.core.logger import logger


# Global flag to enable/disable semantic similarity (fallback to character-based if disabled)
SEMANTIC_ENABLED = True


@lru_cache(maxsize=1)
def _get_model():
    """
    Load sentence-transformers model (cached to avoid re-loading).

    Model: all-MiniLM-L6-v2
    - Size: ~80MB
    - Speed: ~1000 sentences/sec on CPU
    - Quality: Good balance of speed and accuracy

    Returns:
        SentenceTransformer: Loaded model instance

    Raises:
        ImportError: If sentence-transformers not installed
    """
    try:
        from sentence_transformers import SentenceTransformer
        logger.debug("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.debug("✓ Model loaded successfully")
        return model
    except ImportError:
        logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
        raise ImportError(
            "sentence-transformers is required for semantic similarity. "
            "Install with: pip install sentence-transformers>=2.2.0"
        )


def semantic_similarity(text1: str, text2: str, use_semantic: bool = True) -> float:
    """
    Compute semantic similarity between two texts.

    Uses sentence-transformers to generate embeddings and compute cosine similarity.
    Falls back to character-based similarity if semantic is disabled or model fails.

    Args:
        text1: First text to compare
        text2: Second text to compare
        use_semantic: Whether to use semantic similarity (if False, uses character-based)

    Returns:
        float: Similarity score 0.0-1.0
            - 0.0: Completely different
            - 1.0: Identical or semantically equivalent

    Examples:
        >>> semantic_similarity("Subscribe for crypto alerts", "Don't miss our next video - subscribe!")
        0.82  # High semantic similarity despite different wording

        >>> semantic_similarity("Subscribe for updates", "Buy my course for $299")
        0.23  # Low semantic similarity (different intent)
    """
    if not text1 or not text2:
        logger.warning("Empty text provided to semantic_similarity, returning 0.0")
        return 0.0

    # Fallback to character-based similarity if semantic disabled
    if not use_semantic or not SEMANTIC_ENABLED:
        logger.debug("Using character-based similarity (semantic disabled)")
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()

    # Try semantic similarity
    try:
        from sentence_transformers import util

        model = _get_model()

        # Generate embeddings
        embeddings = model.encode([text1, text2], convert_to_tensor=False)

        # Compute cosine similarity
        similarity = float(util.cos_sim(embeddings[0], embeddings[1])[0][0])

        logger.debug(f"Semantic similarity: {similarity:.3f}")
        logger.debug(f"  Text1: {text1[:60]}...")
        logger.debug(f"  Text2: {text2[:60]}...")

        return similarity

    except Exception as e:
        logger.warning(f"Semantic similarity failed: {e}. Falling back to character-based.")
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()


def compare_cta_texts(expected_cta: str, actual_cta: str, use_semantic: bool = True) -> dict:
    """
    Compare two CTA texts and return detailed similarity metrics.

    Useful for debugging and logging CTA matching results.

    Args:
        expected_cta: Expected CTA from CTA Strategist
        actual_cta: Actual CTA from Script Writer
        use_semantic: Whether to use semantic similarity

    Returns:
        dict: Similarity metrics
            - semantic_similarity: float (0.0-1.0)
            - character_similarity: float (0.0-1.0)
            - match_type: str ('exact', 'semantic', 'character', 'none')
            - expected: str (truncated)
            - actual: str (truncated)
    """
    # Compute both types of similarity for comparison
    semantic_sim = semantic_similarity(expected_cta, actual_cta, use_semantic=True)

    from difflib import SequenceMatcher
    character_sim = SequenceMatcher(None, expected_cta, actual_cta).ratio()

    # Determine match type
    if semantic_sim >= 0.95:
        match_type = 'exact'
    elif semantic_sim >= 0.70 and use_semantic:
        match_type = 'semantic'
    elif character_sim >= 0.70:
        match_type = 'character'
    else:
        match_type = 'none'

    return {
        'semantic_similarity': semantic_sim,
        'character_similarity': character_sim,
        'match_type': match_type,
        'expected': expected_cta[:100],
        'actual': actual_cta[:100]
    }


# Preload model on import (optional, for faster first call)
# Uncomment if you want to preload the model:
# try:
#     _get_model()
#     logger.info("✓ Sentence-transformers model preloaded")
# except Exception as e:
#     logger.warning(f"Model preload failed: {e}. Will load on first use.")
