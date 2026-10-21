from types import SimpleNamespace

from kayla.voice.contracts import AudioClip
from kayla.voice.groq_speech import GroqSpeechGenerator, concatenate_wavs, split_for_speech
from kayla.voice.groq_transcriber import GroqTranscriber


def _wav(frames: bytes = b"\x00\x00" * 10) -> bytes:
    import io
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8_000)
        wav.writeframes(frames)
    return buffer.getvalue()


class FakeTranscriptions:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        return SimpleNamespace(text="  Hello Kayla  ")


class FakeSpeech:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def create(self, **request: object) -> SimpleNamespace:
        self.requests.append(request)
        return SimpleNamespace(content=_wav())


def test_groq_transcriber_uploads_the_audio_clip() -> None:
    transcriptions = FakeTranscriptions()
    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions))
    transcriber = GroqTranscriber(client=client, model="whisper-large-v3-turbo")
    clip = AudioClip(data=b"audio", filename="recording.wav")

    transcript = transcriber.transcribe(clip)

    assert transcript == "Hello Kayla"
    assert transcriptions.request == {
        "model": "whisper-large-v3-turbo",
        "file": ("recording.wav", b"audio", "audio/wav"),
    }


def test_groq_speech_generator_requests_wav_audio() -> None:
    speech = FakeSpeech()
    client = SimpleNamespace(audio=SimpleNamespace(speech=speech))
    generator = GroqSpeechGenerator(
        client=client, model="canopylabs/orpheus-v1-english", voice="hannah"
    )

    result = generator.generate("Hello, builder!")

    assert result.filename == "kayla-response.wav"
    assert speech.requests == [
        {
            "model": "canopylabs/orpheus-v1-english",
            "voice": "hannah",
            "input": "Hello, builder!",
            "response_format": "wav",
        }
    ]


def test_groq_speech_generator_chunks_a_long_reply_and_joins_the_wavs() -> None:
    speech = FakeSpeech()
    client = SimpleNamespace(audio=SimpleNamespace(speech=speech))
    generator = GroqSpeechGenerator(client=client, model="tts-model", voice="hannah")
    text = " ".join(f"Sentence number {number} about the project." for number in range(20))

    result = generator.generate(text)

    assert len(speech.requests) > 1
    assert all(len(request["input"]) <= 200 for request in speech.requests)
    # Joined clip holds every chunk's frames.
    import io
    import wave

    with wave.open(io.BytesIO(result.data), "rb") as merged:
        assert merged.getnframes() == 10 * len(speech.requests)


def test_split_for_speech_keeps_short_text_in_one_piece() -> None:
    assert split_for_speech("Short answer.", limit=200) == ["Short answer."]


def test_split_for_speech_breaks_on_sentence_boundaries() -> None:
    text = "First sentence is here. Second sentence follows it. Third one ends it."
    pieces = split_for_speech(text, limit=30)

    assert pieces == [
        "First sentence is here.",
        "Second sentence follows it.",
        "Third one ends it.",
    ]
    assert all(len(piece) <= 30 for piece in pieces)


def test_split_for_speech_hard_splits_an_overlong_word() -> None:
    pieces = split_for_speech("x" * 50, limit=20)

    assert pieces == ["x" * 20, "x" * 20, "x" * 10]


def test_concatenate_wavs_refuses_mismatched_formats() -> None:
    import io
    import wave

    odd = io.BytesIO()
    with wave.open(odd, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(8_000)
        wav.writeframes(b"\x00\x00" * 4)

    try:
        concatenate_wavs([_wav(), odd.getvalue()])
    except RuntimeError as error:
        assert "different formats" in str(error)
    else:
        raise AssertionError("Expected mismatched WAV formats to be rejected")
