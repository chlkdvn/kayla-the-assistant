from kayla.ai.gateway import AIReply
from kayla.conversation.session import ConversationSession
from kayla.voice.contracts import AudioClip
from kayla.voice.workflow import VoiceWorkflow


class FakeChatGateway:
    def reply(self, turns: list[object]) -> AIReply:
        assert [turn.text for turn in turns] == ["Hello Kayla"]
        return AIReply(text="Hello, builder!")


class FakeTranscriber:
    def transcribe(self, audio: AudioClip) -> str:
        assert audio.filename == "microphone.wav"
        return "Hello Kayla"


class FakeSpeechGenerator:
    def generate(self, text: str) -> AudioClip:
        assert text == "Hello, builder!"
        return AudioClip(data=b"generated audio", filename="reply.wav")


def test_voice_workflow_keeps_each_stage_visible() -> None:
    workflow = VoiceWorkflow(
        conversation=ConversationSession(gateway=FakeChatGateway()),
        transcriber=FakeTranscriber(),
        speech_generator=FakeSpeechGenerator(),
    )

    turn = workflow.respond(AudioClip(data=b"recorded audio", filename="microphone.wav"))

    assert turn.transcript == "Hello Kayla"
    assert turn.reply_text == "Hello, builder!"
    assert turn.reply_audio.data == b"generated audio"
