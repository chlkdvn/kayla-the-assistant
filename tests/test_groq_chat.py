from types import SimpleNamespace

from kayla.ai.gateway import ChatTurn
from kayla.ai.groq_chat import GroqChat


class FakeCompletions:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        message = SimpleNamespace(content="Hello from Kayla")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_groq_chat_sends_the_conversation_as_messages() -> None:
    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    chat = GroqChat(
        api_key="unused-in-test",
        base_url="https://example.invalid/v1",
        model="test-model",
        instructions="Be Kayla.",
        client=client,
    )
    turns = [
        ChatTurn(role="user", text="Hello"),
        ChatTurn(role="assistant", text="Hi!"),
        ChatTurn(role="user", text="Remember me?"),
    ]

    reply = chat.reply(turns)

    assert reply.text == "Hello from Kayla"
    assert completions.request == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "Be Kayla."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "Remember me?"},
        ],
    }


def test_groq_chat_builds_a_client_against_the_groq_base_url() -> None:
    client = GroqChat(
        api_key="test-key",
        base_url="https://api.groq.com/openai/v1",
        model="test-model",
        instructions="Be Kayla.",
    )._client

    assert client.api_key == "test-key"
    assert str(client.base_url).rstrip("/") == "https://api.groq.com/openai/v1"
