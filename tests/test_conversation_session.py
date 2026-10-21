from kayla.ai.gateway import AIReply, ChatTurn
from kayla.conversation.session import ConversationSession


class FakeChatGateway:
    def __init__(self) -> None:
        self.calls: list[list[ChatTurn]] = []

    def reply(self, turns: list[ChatTurn]) -> AIReply:
        self.calls.append(turns)
        turn_number = len(self.calls)
        return AIReply(text=f"answer {turn_number}")


def test_session_sends_the_whole_conversation_so_far() -> None:
    gateway = FakeChatGateway()
    session = ConversationSession(gateway=gateway)

    session.send("Hello")
    second_reply = session.send("Do you remember me?")

    assert second_reply.text == "answer 2"
    assert gateway.calls == [
        [ChatTurn(role="user", text="Hello")],
        [
            ChatTurn(role="user", text="Hello"),
            ChatTurn(role="assistant", text="answer 1"),
            ChatTurn(role="user", text="Do you remember me?"),
        ],
    ]


def test_session_reset_starts_a_new_conversation() -> None:
    gateway = FakeChatGateway()
    session = ConversationSession(gateway=gateway)

    session.send("First chat")
    session.reset()
    session.send("New chat")

    assert gateway.calls[-1] == [ChatTurn(role="user", text="New chat")]


def test_session_rejects_an_empty_message() -> None:
    session = ConversationSession(gateway=FakeChatGateway())

    try:
        session.send("   ")
    except ValueError as error:
        assert str(error) == "A message cannot be empty."
    else:
        raise AssertionError("Expected an empty message to be rejected")
