"""The local embedder turns text into a vector with an injected model."""

from __future__ import annotations

from kayla.memory.fastembed_embedder import FastEmbedEmbedder


class FakeTextEmbedding:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[0.1, 0.2, 0.3]]


def test_embedder_calls_the_model_and_returns_plain_floats() -> None:
    model = FakeTextEmbedding()
    embedder = FastEmbedEmbedder(model_name="test-model", model=model)

    vector = embedder.embed("hello there")

    assert vector == [0.1, 0.2, 0.3]
    assert all(isinstance(value, float) for value in vector)
    assert model.calls == [["hello there"]]
