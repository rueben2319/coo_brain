import hashlib
import logging
import math
from typing import List, Optional
import httpx

from app.config import Settings, get_settings

logger = logging.getLogger("coo_brain.embedding")


def _generate_fallback_embedding(text: str, dimension: int = 768) -> List[float]:
    """
    Generates a token-hash bag-of-words pseudo-embedding when Ollama is unreachable.
    Tokens that match between documents and queries produce positive cosine similarity,
    enabling real vector retrieval testing over pgvector without an active LLM instance.
    """
    if not text or not text.strip():
        return [0.0] * dimension

    import re
    tokens = re.findall(r"\w+", text.lower())
    vec = [0.0] * dimension

    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % dimension
        sign = 1.0 if ((h >> 16) & 1) else -1.0
        vec[idx] += sign

    # Add minor text hash smoothing
    hasher = hashlib.sha256(text.encode("utf-8"))
    seed_bytes = hasher.digest()
    for i in range(min(len(seed_bytes), dimension)):
        vec[i] += (seed_bytes[i] / 255.0) * 0.05

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _normalize_dimension(vector: List[float], target_dim: int) -> List[float]:
    """Ensures vector matches target_dim by padding or truncating and L2-normalizing."""
    if len(vector) == target_dim:
        return vector
    if len(vector) > target_dim:
        vector = vector[:target_dim]
    else:
        vector = vector + [0.0] * (target_dim - len(vector))

    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector


class EmbeddingService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.effective_embed_base_url.rstrip("/")
        self.model = self.settings.ollama_embed_model
        self.dimension = self.settings.vector_dimension
        self.api_key = self.settings.ollama_api_key

    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def get_embedding(self, text: str) -> List[float]:
        results = await self.get_embeddings([text])
        return results[0] if results else _generate_fallback_embedding(text, self.dimension)

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        embeddings: List[List[float]] = []
        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # 1. Try Ollama newer /api/embed endpoint
                embed_url = f"{self.base_url}/embed"
                payload = {"model": self.model, "input": texts}
                response = await client.post(embed_url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    raw_embeddings = data.get("embeddings", [])
                    if raw_embeddings:
                        return [_normalize_dimension(vec, self.dimension) for vec in raw_embeddings]

                # 2. Try single Ollama /api/embeddings for each text
                single_url = f"{self.base_url}/embeddings"
                for text in texts:
                    res = await client.post(
                        single_url,
                        json={"model": self.model, "prompt": text},
                        headers=headers,
                    )
                    if res.status_code == 200:
                        vec = res.json().get("embedding", [])
                        embeddings.append(_normalize_dimension(vec, self.dimension))
                    else:
                        logger.warning(
                            f"Ollama embeddings call failed ({res.status_code}): {res.text}. Falling back to deterministic embedding."
                        )
                        embeddings.append(_generate_fallback_embedding(text, self.dimension))

                if embeddings:
                    return embeddings

            except Exception as e:
                logger.warning(
                    f"Could not connect to Ollama embedding service at {self.base_url}: {e}. "
                    "Using deterministic fallback embedding for development/testing."
                )

        # Fallback if connection fails
        return [_generate_fallback_embedding(t, self.dimension) for t in texts]


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
