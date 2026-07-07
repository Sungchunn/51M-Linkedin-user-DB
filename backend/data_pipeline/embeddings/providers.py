"""
INSIGHT - Embedding Providers
OpenAI API integration for generating embeddings

Negative Spaces Implementation:
- Validates API key exists
- Enforces dimension constraints (1536)
- Batch size limits (max 100 per request)
- Retry logic for API failures
"""

import os
from typing import List, Optional
import logging
from openai import OpenAI, OpenAIError
from backend.data_pipeline.embeddings.retry import retry_decorator

logger = logging.getLogger(__name__)

# Sentinel for uninitialized client
UNINITIALIZED = object()


class EmbeddingProviderError(Exception):
    """Raised when embedding generation fails"""
    pass


class OpenAIEmbeddingProvider:
    """
    OpenAI embedding provider using text-embedding-3-small.

    NEGATIVE SPACE CONTRACT:
    - API key must be set before use
    - Batch size must be <= 100 (OpenAI limit)
    - Returns exactly 1536-dimensional vectors
    - Never returns empty list for non-empty input
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize OpenAI provider.

        NEGATIVE SPACE CONTRACT:
        - api_key must be valid or loadable from env
        - model defaults to text-embedding-3-small

        Args:
            api_key: OpenAI API key (or uses OPENAI_API_KEY env var)
            model: Embedding model name

        Raises:
            EmbeddingProviderError: If API key is missing
        """
        # Load from env if not provided
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')

        if not self.api_key:
            raise EmbeddingProviderError(
                "NEGATIVE SPACE VIOLATION: OPENAI_API_KEY not found in environment or parameters"
            )

        # Initialize client
        self.client = OpenAI(api_key=self.api_key)

        # Model configuration
        self.model = model or os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
        self.dimension = int(os.getenv('EMBEDDING_DIMENSION', '1536'))

        # Validate dimension
        if self.dimension != 1536:
            raise EmbeddingProviderError(
                f"NEGATIVE SPACE VIOLATION: Only 1536-dim embeddings supported, got {self.dimension}"
            )

        logger.info(f"✅ OpenAI provider initialized: model={self.model}, dim={self.dimension}")

    @retry_decorator(max_retries=3, base_delay=1.0, exceptions=(OpenAIError, Exception))
    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Generate embeddings for a batch of texts.

        NEGATIVE SPACE CONTRACT:
        - texts must not be empty
        - batch size must be <= 100 (OpenAI limit)
        - Returns list of 1536-dim vectors or None on failure
        - Output length matches input length

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors or None on failure
        """
        # Validate inputs
        if not texts:
            raise EmbeddingProviderError(
                "NEGATIVE SPACE VIOLATION: Cannot embed empty text list"
            )

        if len(texts) > 100:
            raise EmbeddingProviderError(
                f"NEGATIVE SPACE VIOLATION: Batch size {len(texts)} exceeds OpenAI limit of 100"
            )

        # Filter out empty strings
        valid_texts = [t for t in texts if t and t.strip()]

        if len(valid_texts) != len(texts):
            logger.warning(
                f"NEGATIVE SPACE: Filtered {len(texts) - len(valid_texts)} empty strings from batch"
            )

        if not valid_texts:
            logger.error("NEGATIVE SPACE: All texts in batch are empty")
            return None

        try:
            logger.debug(f"Embedding batch of {len(valid_texts)} texts")

            # Call OpenAI API
            response = self.client.embeddings.create(
                input=valid_texts,
                model=self.model
            )

            # Extract embeddings
            embeddings = [item.embedding for item in response.data]

            # Validate output
            if len(embeddings) != len(valid_texts):
                raise EmbeddingProviderError(
                    f"NEGATIVE SPACE VIOLATION: Expected {len(valid_texts)} embeddings, "
                    f"got {len(embeddings)}"
                )

            # Validate dimensions
            for i, emb in enumerate(embeddings):
                if len(emb) != self.dimension:
                    raise EmbeddingProviderError(
                        f"NEGATIVE SPACE VIOLATION: Embedding {i} has {len(emb)} dims, "
                        f"expected {self.dimension}"
                    )

            logger.debug(f"✅ Successfully embedded {len(embeddings)} texts")

            return embeddings

        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise  # Let retry decorator handle it

        except Exception as e:
            logger.error(f"Unexpected error during embedding: {e}", exc_info=True)
            raise

    def embed_single(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.

        NEGATIVE SPACE CONTRACT:
        - text must not be empty
        - Returns 1536-dim vector or None on failure

        Args:
            text: Text string to embed

        Returns:
            Embedding vector or None on failure
        """
        if not text or not text.strip():
            logger.warning("NEGATIVE SPACE: Attempted to embed empty text")
            return None

        embeddings = self.embed_batch([text])

        if embeddings is None or len(embeddings) == 0:
            return None

        return embeddings[0]

    def validate_embedding(self, embedding: List[float]) -> bool:
        """
        Validate embedding vector.

        NEGATIVE SPACE CONTRACT:
        - Must be exactly 1536 dimensions
        - All values must be numeric (float)

        Args:
            embedding: Embedding vector to validate

        Returns:
            True if valid, False otherwise
        """
        if not embedding:
            logger.warning("NEGATIVE SPACE: Empty embedding")
            return False

        if len(embedding) != self.dimension:
            logger.warning(
                f"NEGATIVE SPACE: Embedding has {len(embedding)} dims, expected {self.dimension}"
            )
            return False

        # Check all values are numeric
        for i, val in enumerate(embedding):
            if not isinstance(val, (int, float)):
                logger.warning(
                    f"NEGATIVE SPACE: Embedding[{i}] is {type(val)}, expected float"
                )
                return False

        return True


# Global provider instance (lazy initialization)
_provider: Optional[OpenAIEmbeddingProvider] = None


def get_provider() -> OpenAIEmbeddingProvider:
    """
    Get or create global embedding provider.

    NEGATIVE SPACE CONTRACT:
    - Returns initialized provider
    - Raises error if initialization fails

    Returns:
        OpenAIEmbeddingProvider instance

    Raises:
        EmbeddingProviderError: If provider cannot be initialized
    """
    global _provider

    if _provider is None:
        _provider = OpenAIEmbeddingProvider()

    return _provider


def embed_texts(texts: List[str]) -> Optional[List[List[float]]]:
    """
    Convenience function to embed texts using global provider.

    NEGATIVE SPACE CONTRACT:
    - texts must not be empty
    - Returns embeddings or None on failure

    Args:
        texts: List of text strings

    Returns:
        List of embedding vectors or None
    """
    provider = get_provider()
    return provider.embed_batch(texts)


def embed_text(text: str) -> Optional[List[float]]:
    """
    Convenience function to embed single text using global provider.

    NEGATIVE SPACE CONTRACT:
    - text must not be empty
    - Returns embedding or None on failure

    Args:
        text: Text string

    Returns:
        Embedding vector or None
    """
    provider = get_provider()
    return provider.embed_single(text)
