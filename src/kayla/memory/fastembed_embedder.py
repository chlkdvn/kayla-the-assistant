"""Local embedding model for long-term memory, powered by fastembed (ONNX).

Runs entirely on this machine: no API key, no per-call network traffic. The
model is downloaded once on first use and cached locally.
"""

from __future__ import annotations

from typing import Any

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class FastEmbedEmbedder:
    """Turn text into a vector with a local embedding model."""

    def __init__(self, *, model_name: str = DEFAULT_MODEL, model: Any | None = None) -> None:
        if model is None:
            from fastembed import TextEmbedding

            model = TextEmbedding(model_name=model_name)
        self._model = model

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for one piece of text."""
        vector = next(iter(self._model.embed([text])))
        return [float(value) for value in vector]
