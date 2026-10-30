"""Units for Kayla's spoken behaviour-mode allowlist and directives."""

from __future__ import annotations

from kayla.realtime.modes import MODES, QUIET_MODES, mode_directive, parse_mode


def test_every_requested_mode_word_parses() -> None:
    for words, expected in (
        ("shutup", "shutup"),
        ("shut up", "shutup"),
        ("be quiet", "shutup"),
        ("stop listening", "shutup"),
        ("stop hearing me", "shutup"),
        ("standby", "standby"),
        ("stand by", "standby"),
        ("speak", "speak"),
        ("talk to me", "speak"),
        ("listen again", "speak"),
        ("start listening", "speak"),
        ("listen to me", "speak"),
        ("be serious", "serious"),
        ("be playful", "playful"),
        ("be helpful", "helpful"),
        ("get to work", "work"),
        ("work mode", "work"),
    ):
        assert parse_mode(words) == expected


def test_name_prefix_and_punctuation_still_parse() -> None:
    assert parse_mode("Kayla, shut up!") == "shutup"
    assert parse_mode("Be serious.") == "serious"


def test_ordinary_sentences_are_not_commands() -> None:
    assert parse_mode("be seriously good at math") is None
    assert parse_mode("what is the weather like today") is None
    assert parse_mode("") is None


def test_quiet_kinds_and_tone_kinds_are_disjoint() -> None:
    assert QUIET_MODES <= MODES
    assert not (QUIET_MODES & {"serious", "playful", "helpful", "work", "speak"})


def test_every_mode_has_a_directive() -> None:
    for mode in MODES:
        text = mode_directive(mode)
        assert "CURRENT MODE" in text
