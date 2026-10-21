"""Groq chat-completions implementation of Kayla's chat gateway.

Groq is OpenAI-compatible, so the OpenAI SDK talks to it with a different
base URL. The conversation history is sent with every turn because Groq's
API does not keep server-side conversation state.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from kayla.ai.gateway import AIReply, ChatTurn


class GroqChat:
    """Translate Kayla's small chat contract into Groq SDK calls."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        instructions: str,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._instructions = instructions
        self._client = client if client is not None else OpenAI(api_key=api_key, base_url=base_url)

    def reply(self, turns: list[ChatTurn]) -> AIReply:
        """Send the conversation so far and return the next assistant message."""
        messages: list[dict[str, str]] = [{"role": "system", "content": self._instructions}]
        messages.extend({"role": turn.role, "content": turn.text} for turn in turns)

        response = self._client.chat.completions.create(model=self._model, messages=messages)
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            raise RuntimeError("Groq returned a response without displayable text.")

        return AIReply(text=answer)
