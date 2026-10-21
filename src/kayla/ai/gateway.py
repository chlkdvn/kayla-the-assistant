"""Provider-independent types used by the conversation layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """One message in the conversation so far, provider-independent."""

    role: str  # "user" or "assistant"
    text: str


@dataclass(frozen=True, slots=True)
class AIReply:
    """The small part of an AI response the application needs."""

    text: str


class ChatGateway(Protocol):
    """Contract implemented by any conversational AI provider."""

    def reply(self, turns: list[ChatTurn]) -> AIReply:
        """Return the next assistant response given the whole conversation."""
        ...
