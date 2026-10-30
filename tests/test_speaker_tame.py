"""Offline tests for the speaker volume trim and anti-peak limiter."""

from __future__ import annotations

from array import array

from kayla.realtime.audio import (
    DEFAULT_SPEAKER_CEILING,
    SOFT_KNEE,
    tame_speaker_audio,
)


def pcm(samples: list[int]) -> bytes:
    out = array("h")
    out.extend(samples)
    return out.tobytes()


def samples(data: bytes) -> list[int]:
    out = array("h")
    out.frombytes(data)
    return out.tolist()


def test_scales_the_gain_on_quiet_audio() -> None:
    # 0.5 gain trims a quiet wave exactly; quieter samples are pure scaling.
    assert samples(tame_speaker_audio(pcm([1000, -2000, 500]), gain=0.5)) == [500, -1000, 250]


def test_gain_one_reproduces_quiet_audio_exactly() -> None:
    shape = [-26000, -12000, 0, 7000, 26000]  # everything at or below the knee
    assert samples(tame_speaker_audio(pcm(shape), gain=1.0)) == shape


def test_peaks_bend_toward_the_ceiling_not_byte_max() -> None:
    # Full-scale audio must never square off to int16 max: the limiter bends
    # it to a value clearly below the ceiling and symmetric on both signs.
    out = samples(tame_speaker_audio(pcm([SOFT_KNEE - 1, SOFT_KNEE, 32767, -32767]), gain=1.0))
    assert out[0] == SOFT_KNEE - 1  # at the knee: untouched
    assert out[1] == SOFT_KNEE  # the knee itself: untouched
    assert 0 < out[2] < DEFAULT_SPEAKER_CEILING <= 32767
    assert 0 > out[3] > -DEFAULT_SPEAKER_CEILING


def test_amplifying_loud_audio_stays_inside_the_ceiling() -> None:
    wave = pcm([0, 12000, 22000])
    out = samples(tame_speaker_audio(wave, gain=2.0))
    assert all(abs(s) <= DEFAULT_SPEAKER_CEILING for s in out)
    assert abs(out[2]) < abs(out[1]) * 2  # compression, not straight clipping


def test_compression_keeps_the_shape_monotonic() -> None:
    wave = pcm([10000, 20000, 26000, 28000, 30000, 32000])
    out = samples(tame_speaker_audio(wave, gain=1.0))
    assert out == sorted(out)  # louder in means louder out; no fold-back


def test_odd_trailing_byte_is_dropped() -> None:
    data = pcm([300]) + b"\x01"  # half a sample on the end
    out = tame_speaker_audio(data, gain=1.0)
    assert samples(out) == [300]


def test_empty_audio_stays_empty() -> None:
    assert tame_speaker_audio(b"", gain=0.8) == b""


def test_silence_is_untouched() -> None:
    assert samples(tame_speaker_audio(pcm([0, 0, 0]), gain=0.8)) == [0, 0, 0]
