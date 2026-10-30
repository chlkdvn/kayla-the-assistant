"""The embedding model must live in the home cache, not /tmp.

``/tmp`` is wiped on reboot: a model cached there would be re-downloaded -
and re-paid over a phone tether - on every restart. These tests pin the
cache location without touching the real fastembed package or the network.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

from kayla.memory import fastembed_embedder


class _RecordingTextEmbedding:
    """Stands in for fastembed.TextEmbedding and records how it was built."""

    last_kwargs: dict[str, object] | None = None

    def __init__(self, **kwargs: object) -> None:
        _RecordingTextEmbedding.last_kwargs = kwargs

    def embed(self, texts: list[str]):
        return iter([[0.1, 0.2] for _ in texts])


def test_embedder_uses_the_persistent_home_cache(monkeypatch):
    module = types.ModuleType("fastembed")
    module.TextEmbedding = _RecordingTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)

    fastembed_embedder.FastEmbedEmbedder()

    kwargs = _RecordingTextEmbedding.last_kwargs
    assert kwargs is not None
    cached = Path(str(kwargs["cache_dir"]))
    assert cached == fastembed_embedder.home_cache_dir()
    assert cached.parts[1] != "tmp"  # relocated out of /tmp for good


def test_explicit_cache_dir_wins(monkeypatch):
    module = types.ModuleType("fastembed")
    module.TextEmbedding = _RecordingTextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)

    fastembed_embedder.FastEmbedEmbedder(cache_dir="/somewhere/else")

    assert _RecordingTextEmbedding.last_kwargs["cache_dir"] == "/somewhere/else"


def test_embed_returns_plain_floats():
    embedder = fastembed_embedder.FastEmbedEmbedder(model=_RecordingTextEmbedding())

    assert embedder.embed("hello") == [0.1, 0.2]
