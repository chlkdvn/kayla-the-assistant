"""Construct the concrete components used by Kayla's voice interface."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from kayla.ai.groq_chat import GroqChat
from kayla.config.settings import Settings
from kayla.conversation.session import ConversationSession
from kayla.prompts.kayla_personality import build_kayla_instructions
from kayla.voice.contracts import AudioPlayer, AudioRecorder
from kayla.voice.groq_speech import GroqSpeechGenerator
from kayla.voice.groq_transcriber import GroqTranscriber
from kayla.voice.microphone import SoundDeviceMicrophone
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
    client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    chat = GroqChat(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.chat_model,
        instructions=build_kayla_instructions(settings.robot_name),
        client=client,
    )
    conversation = ConversationSession(gateway=chat)
    workflow = VoiceWorkflow(
        conversation=conversation,
        transcriber=GroqTranscriber(client=client, model=settings.transcription_model),
        speech_generator=GroqSpeechGenerator(
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
