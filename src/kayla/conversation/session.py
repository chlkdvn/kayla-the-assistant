"""Manage conversation state without depending on a specific AI provider."""

from __future__ import annotations

from dataclasses import dataclass, field

from kayla.ai.gateway import AIReply, ChatGateway, ChatTurn


@dataclass(slots=True)
class ConversationSession:
    """A single multi-turn conversation between one human and Kayla."""

    gateway: ChatGateway
    _history: list[ChatTurn] = field(default_factory=list, init=False, repr=False)

    def send(self, user_text: str) -> AIReply:
        """Validate and send a user message, then remember the whole exchange."""
        message = user_text.strip()
        if not message:
            raise ValueError("A message cannot be empty.")

        outgoing = [*self._history, ChatTurn(role="user", text=message)]
        reply = self.gateway.reply(outgoing)
        self._history = [*outgoing, ChatTurn(role="assistant", text=reply.text)]
        return reply

    def reset(self) -> None:
        """Forget the conversation so far and begin a new chat."""
        self._history.clear()
