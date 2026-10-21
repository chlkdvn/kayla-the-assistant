"""Groq text-to-speech implementation.

Groq's TTS model (Orpheus) accepts at most 200 characters per request, so
longer answers are split on sentence boundaries, synthesized piece by piece,
and the WAV chunks are stitched back into one clip before playback.
"""

from __future__ import annotations

import io
import re
import wave
from typing import Any

from kayla.voice.contracts import AudioClip

_MAX_INPUT_CHARS = 200


class GroqSpeechGenerator:
    """Generate Kayla's spoken answer as one WAV audio clip."""

    def __init__(self, *, client: Any, model: str, voice: str) -> None:
        self._client = client
        self._model = model
        self._voice = voice

    def generate(self, text: str) -> AudioClip:
        """Generate a complete WAV response suitable for local playback."""
        chunks = split_for_speech(text, limit=_MAX_INPUT_CHARS)
        parts = [self._speak(chunk) for chunk in chunks]
        audio_data = parts[0] if len(parts) == 1 else concatenate_wavs(parts)
        if not audio_data:
            raise RuntimeError("Groq returned an empty speech response.")
        return AudioClip(data=audio_data, filename="kayla-response.wav")

    def _speak(self, text: str) -> bytes:
        response = self._client.audio.speech.create(
            model=self._model,
            voice=self._voice,
            input=text,
            response_format="wav",
        )
        audio_data = response.content
        if not audio_data:
            raise RuntimeError("Groq returned an empty speech response.")
        return audio_data


def split_for_speech(text: str, *, limit: int) -> list[str]:
    """Split text into pieces no longer than ``limit`` characters.

    Sentences are kept whole when they fit; longer sentences break at word
    boundaries, and any single overlong word is hard-split.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    sentences = re.split(r"(?<=[.!?…])\s+", text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
            current = ""
        pieces.extend(_split_oversized(sentence, limit))
    if current:
        pieces.append(current)
    return pieces


def _split_oversized(sentence: str, limit: int) -> list[str]:
    """Break one over-long sentence at word boundaries, then hard-split words."""
    pieces: list[str] = []
    current = ""
    for word in sentence.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
        current = word
    if current:
        pieces.append(current)
    return [piece for part in pieces for piece in _hard_split(part, limit)]


def _hard_split(piece: str, limit: int) -> list[str]:
    """Last resort for a single word longer than the limit."""
    if len(piece) <= limit:
        return [piece]
    return [piece[index : index + limit] for index in range(0, len(piece), limit)]


def concatenate_wavs(chunks: list[bytes]) -> bytes:
    """Join same-format WAV chunks into one clip by appending their frames."""
    if not chunks:
        raise RuntimeError("No speech chunks to join.")
    output = io.BytesIO()
    with wave.open(output, "wb") as merged:
        with wave.open(io.BytesIO(chunks[0]), "rb") as first:
            merged_params = first.getparams()
            merged.setparams(merged_params)
            merged.writeframes(first.readframes(first.getnframes()))
        for chunk in chunks[1:]:
            with wave.open(io.BytesIO(chunk), "rb") as part:
                if part.getparams() != merged_params:
                    raise RuntimeError("Cannot join speech chunks with different formats.")
                merged.writeframes(part.readframes(part.getnframes()))
    return output.getvalue()
