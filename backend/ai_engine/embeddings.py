"""Text embeddings for semantic search and duplicate detection.

The vector size is fixed by the database column (384), so every embedder here produces 384 values,
L2-normalised so cosine distance and dot product agree.
"""

import hashlib
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

DIMENSIONS = 384


class Embedder(Protocol):
    name: str
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FastEmbedEmbedder:
    """Local ONNX embedding model (default BAAI/bge-small-en-v1.5, 384 dimensions). Free and offline
    after the first download."""

    name = "fastembed"

    def __init__(self, model: str, cache_dir: Path | None = None) -> None:
        from fastembed import TextEmbedding

        self.model = model
        self._model = TextEmbedding(model_name=model, cache_dir=str(cache_dir) if cache_dir else None)
        probe = next(iter(self._model.embed(["dimension probe"])))
        self.dimensions = len(probe)
        if self.dimensions != DIMENSIONS:
            raise ValueError(
                f"Embedding model {model} produces {self.dimensions} dimensions; the database expects {DIMENSIONS}"
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [_normalise([float(x) for x in v]) for v in self._model.embed(texts, batch_size=32)]


class HashEmbedder:
    """Deterministic bag-of-words hashing. A test double only: it matches wording, not meaning.
    Settings refuse it in production."""

    name = "hash"
    model = "hash-v1"
    dimensions = DIMENSIONS

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vector = [0.0] * DIMENSIONS
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % DIMENSIONS
                vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
            out.append(_normalise(vector))
        return out


@lru_cache
def build_embedder(provider: str, model: str, cache_dir: str | None) -> Embedder:
    if provider == "hash":
        return HashEmbedder()
    if provider == "fastembed":
        return FastEmbedEmbedder(model, Path(cache_dir) if cache_dir else None)
    raise ValueError(f"Unknown embedding provider {provider}")


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
