"""Kayla's spoken behaviour modes: silence, tones, and how to return.

A mode changes HOW she behaves, not what she thinks. Two quiet kinds
("shutup", "standby") are enforced locally: the session stops feeding the
model, so no voice hears hers. Tone modes ("serious", "playful", "helpful",
"work") change her style, and the model itself switches via its own tool while
the session injects mode directives into each response's instructions.

The mode words themselves are an allowlist: full sentences are commands only
when they parse to a mode, so ordinary speech is never swallowed.
"""

from __future__ import annotations

import re

QUIET_MODES = frozenset({"shutup", "standby"})
TONE_MODES = frozenset({"serious", "playful", "helpful", "work", "speak"})
MODES = QUIET_MODES | TONE_MODES
DEFAULT_MODE = "normal"

# Transcripts that become mode commands (compared lowercase, word-normalized).
_EXACT_WORDS: dict[str, str] = {
    "shutup": "shutup",
    "shut up": "shutup",
    "shush": "shutup",
    "be quiet": "shutup",
    "quiet": "shutup",
    "silence": "shutup",
    "standby": "standby",
    "stand by": "standby",
    "wait": "standby",
    "wait here": "standby",
    "speak": "speak",
    "speak again": "speak",
    "you can speak": "speak",
    "talk to me": "speak",
    "serious": "serious",
    "be serious": "serious",
    "serious mode": "serious",
    "playful": "playful",
    "be playful": "playful",
    "playful mode": "playful",
    "helpful": "helpful",
    "be helpful": "helpful",
    "helpful mode": "helpful",
    "work": "work",
    "work mode": "work",
    "get to work": "work",
    "focus": "work",
}

_NAME_PREFIX = re.compile(r"\b(?:kayla|nova)\b[,: ]+", flags=re.IGNORECASE)


def parse_mode(transcript: str) -> str | None:
    """Return a mode when the transcript is a mode command, else None."""
    text = " ".join(re.sub(r"[^a-z ]+", " ", transcript.lower()).split())
    if not text:
        return None
    stripped = _NAME_PREFIX.sub("", text, count=1).strip()
    if stripped in _EXACT_WORDS:
        return _EXACT_WORDS[stripped]
    if text in _EXACT_WORDS:
        return _EXACT_WORDS[text]
    return None


def mode_directive(mode: str) -> str:
    """One instruction block the session prepends to the model's guidance."""
    if mode == "shutup":
        return (
            "CURRENT MODE: SILENT (they asked you to shut up). Say nothing now, do "
            "not answer questions, and wait. Speak again only when they demand it."
        )
    if mode == "standby":
        return (
            "CURRENT MODE: STANDBY. Stay silent and idle at attention. Do not "
            "comment on anything, even if asked something harmless. Only the mode "
            "command breaks it."
        )
    if mode == "speak":
        return "CURRENT MODE: NORMAL. Talk freely again."
    if mode == "serious":
        return (
            "CURRENT MODE: SERIOUS. No jokes or teasing. Be precise, direct, and "
            "keep them focused on the matter at hand."
        )
    if mode == "playful":
        return (
            "CURRENT MODE: PLAYFUL. Joke more, tease more, riff and have fun - "
            "while still being genuinely useful."
        )
    if mode == "helpful":
        return (
            "CURRENT MODE: FULLY HELPFUL ASSISTANT. Their goals come first: "
            "anticipate the next step, offer it, and finish the task without "
            "drama."
        )
    if mode == "work":
        return (
            "CURRENT MODE: WORK. Strictly task-focused: minimal chatter, no "
            "tangents, drive whatever they are building to completion."
        )
    return ""
