"""Construct the concrete components used by Kayla's realtime interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from kayla.config.settings import ConfigurationError, Settings
from kayla.prompts.kayla_personality import build_kayla_realtime_instructions
from kayla.realtime.audio import StreamingMicrophone, StreamingSpeaker
from kayla.realtime.events import RealtimeDisplayEvent
from kayla.realtime.options import RealtimeSessionOptions

if TYPE_CHECKING:
    from kayla.realtime.gemini_session import GeminiVoiceSession


def build_realtime_session(
    settings: Settings,
    *,
    on_event: Callable[[RealtimeDisplayEvent], None],
    face: object | None = None,
) -> GeminiVoiceSession:
    """Create live audio I/O and the persistent Gemini Live session."""
    from kayla.realtime.gemini_session import GEMINI_INPUT_RATE, GEMINI_OUTPUT_RATE

    if not settings.gemini_api_key:
        raise ConfigurationError(
            "Her voice runs on Google Gemini, which needs GEMINI_API_KEY in your .env. "
            "Get a free one at https://aistudio.google.com/apikey."
        )
    options = RealtimeSessionOptions.from_settings(settings)
    microphone = StreamingMicrophone(
        sample_rate=GEMINI_INPUT_RATE,
        device=settings.audio_input_device,
    )
    speaker = StreamingSpeaker(
        sample_rate=GEMINI_OUTPUT_RATE,
        device=settings.audio_output_device,
    )
    camera = None
    if settings.vision_enabled:
        from kayla.vision.camera import OpenCVCamera

        camera = OpenCVCamera(
            device_index=settings.camera_device_index,
            max_width=settings.vision_image_max_width,
        )
    screen = None
    if settings.screen_enabled:
        from kayla.vision.screen import GrimScreen

        screen = GrimScreen(max_width=settings.screen_max_width)
    memory = None
    if settings.memory_enabled:
        # Embedding runs locally (fastembed); degrade to no memory if the model
        # cannot load rather than failing to start.
        try:
            from pathlib import Path

            from kayla.memory.fastembed_embedder import FastEmbedEmbedder
            from kayla.memory.store import MemoryStore

            embedder = FastEmbedEmbedder(model_name=settings.embedding_model)
            memory = MemoryStore(
                embedder=embedder,
                path=Path(settings.memory_path),
                top_k=settings.memory_top_k,
            )
        except Exception as error:  # noqa: BLE001 - memory is optional; keep her running
            print(f"Long-term memory is off ({error}); continuing.")
    browser = None
    if settings.browser_enabled:
        from kayla.system.browser import Browser

        browser = Browser()
    shell = None
    launcher = None
    keyboard = None
    if settings.shell_enabled:
        from kayla.system.keyboard import Keyboard
        from kayla.system.launcher import TerminalLauncher
        from kayla.system.shell import ShellRunner

        shell = ShellRunner(
            timeout=settings.shell_timeout_seconds,
            block_dangerous=settings.shell_block_dangerous,
        )
        launcher = TerminalLauncher(
            terminal=settings.terminal_command,
            block_dangerous=settings.shell_block_dangerous,
        )
        keyboard = Keyboard(tool=settings.keyboard_tool)
    echo_canceller = None
    if settings.realtime_echo_cancel:
        from kayla.realtime.echo_cancel import PulseEchoCanceller

        echo_canceller = PulseEchoCanceller()
    from kayla.system.environment import describe_environment

    shared: dict[str, object | None] = dict(
        instructions=build_kayla_realtime_instructions(
            settings.robot_name, environment=describe_environment()
        ),
        options=options,
        microphone=microphone,
        speaker=speaker,
        on_event=on_event,
        half_duplex=settings.realtime_half_duplex,
        camera=camera,
        screen=screen,
        memory=memory,
        auto_capture_memory=settings.memory_auto_capture,
        browser=browser,
        shell=shell,
        launcher=launcher,
        keyboard=keyboard,
        echo_canceller=echo_canceller,
        face=face,
    )
    from kayla.realtime.gemini_session import GeminiVoiceSession

    return GeminiVoiceSession(
        api_key=settings.gemini_api_key,
        model=settings.gemini_realtime_model,
        voice=settings.gemini_voice,
        affective_dialog=settings.gemini_affective_dialog,
        tone_cues=settings.tone_cues_enabled,
        **shared,
    )
