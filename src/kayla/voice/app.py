"""Construct the concrete components used by Kayla's voice interface."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from kayla.ai.openai_chat import OpenAIChat
from kayla.config.settings import ConfigurationError, Settings
from kayla.conversation.session import ConversationSession
from kayla.prompts.kayla_personality import build_kayla_instructions
from kayla.voice.contracts import AudioPlayer, AudioRecorder
from kayla.voice.microphone import SoundDeviceMicrophone
from kayla.voice.openai_speech import OpenAISpeechGenerator
from kayla.voice.openai_transcriber import OpenAITranscriber
from kayla.voice.speaker import SoundDeviceSpeaker
from kayla.voice.workflow import VoiceWorkflow


@dataclass(frozen=True, slots=True)
class VoiceApplication:
    """The components needed by a voice-facing user interface."""

    workflow: VoiceWorkflow
    recorder: AudioRecorder
    player: AudioPlayer


def build_voice_application(settings: Settings) -> VoiceApplication:
    """Create the chained voice workflow and local audio devices."""
    if not settings.openai_api_key:
        raise ConfigurationError(
            "Push-to-talk voice runs on OpenAI, which needs OPENAI_API_KEY in your .env. "
            "For the free Gemini voice mode instead, run:  uv run kayla-realtime"
        )
    client = OpenAI(api_key=settings.openai_api_key)
    chat = OpenAIChat(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        instructions=build_kayla_instructions(settings.robot_name),
        client=client,
    )
    conversation = ConversationSession(gateway=chat)
    workflow = VoiceWorkflow(
        conversation=conversation,
        transcriber=OpenAITranscriber(client=client, model=settings.transcription_model),
        speech_generator=OpenAISpeechGenerator(
            client=client,
            model=settings.speech_model,
            voice=settings.speech_voice,
        ),
    )
    recorder = SoundDeviceMicrophone(
        sample_rate=settings.microphone_sample_rate,
        device=settings.audio_input_device,
    )
    player = SoundDeviceSpeaker(device=settings.audio_output_device)
    return VoiceApplication(workflow=workflow, recorder=recorder, player=player)
