"""Local embedding model for long-term memory, powered by fastembed (ONNX).

Runs entirely on this machine: no API key, no per-call network traffic. The
model is downloaded once on first use and cached in ``~/.cache/kayla/embeddings``
- a home directory, never ``/tmp``, because a workstation reboot wipes ``/tmp``
and would make her re-download (and pay for it again) on every restart.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def home_cache_dir() -> Path:
    """The persistent cache directory for the embedding model."""
    return Path.home() / ".cache" / "kayla" / "embeddings"


class FastEmbedEmbedder:
    """Turn text into a vector with a local embedding model."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        model: Any | None = None,
        cache_dir: Path | str | None = None,
    ) -> None:
        if model is None:
            from fastembed import TextEmbedding

            target = Path(cache_dir) if cache_dir is not None else home_cache_dir()
            model = TextEmbedding(model_name=model_name, cache_dir=str(target))
        self._model = model

    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for one piece of text."""
        vector = next(iter(self._model.embed([text])))
        return [float(value) for value in vector]
