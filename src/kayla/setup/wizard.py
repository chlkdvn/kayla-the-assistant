"""The pure logic of first-run setup: turn answers into a complete .env file.

This module has NO input(), no filesystem, and no network so it is trivially
testable. `cli.py` gathers the answers interactively and does the actual I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

FREE_GEMINI_KEY_URL = "https://aistudio.google.com/apikey"


@dataclass(frozen=True, slots=True)
class Answers:
    """Everything the wizard needs to write a working configuration."""

    gemini_api_key: str
    openai_api_key: str = ""
    robot_name: str = "Kayla"
    audio_input_device: str = ""
    audio_output_device: str = ""
    wake_enabled: bool = False
    wake_model_path: str = ""
    screen_enabled: bool = False
    body_enabled: bool = False
    body_port: str = ""
    shell_enabled: bool = False
    face_enabled: bool = True


def _b(value: bool) -> str:
    return "true" if value else "false"


def build_env_text(a: Answers) -> str:
    """Render a complete, ready-to-run .env from the wizard's answers.

    Pure function: given the same answers it always returns the same text, so the
    whole configuration step can be unit-tested without prompts or files.
    """
    lines = [
        "# Written by `kayla-setup`. Holds your private keys - never commit this file.",
        "",
        "# Her brain: Gemini Live (free key, cheaper audio).",
        "KAYLA_REALTIME_PROVIDER=gemini",
        f"GEMINI_API_KEY={a.gemini_api_key}",
        "# Optional - only long-term memory + the push-to-talk voice mode use this.",
        f"OPENAI_API_KEY={a.openai_api_key}",
        f"KAYLA_NAME={a.robot_name}",
        "",
        "# Gemini voice.",
        "KAYLA_GEMINI_REALTIME_MODEL=gemini-3.1-flash-live-preview",
        "KAYLA_GEMINI_VOICE=Leda",
        "KAYLA_TONE_CUES_ENABLED=true",
        "",
        "# Audio (blank = system default).",
        f"KAYLA_AUDIO_INPUT_DEVICE={a.audio_input_device}",
        f"KAYLA_AUDIO_OUTPUT_DEVICE={a.audio_output_device}",
        "KAYLA_REALTIME_HALF_DUPLEX=true",
        "KAYLA_REALTIME_ECHO_CANCEL=false",
        "",
        "# Vision (photo only when she calls her look tool; fine with no camera).",
        "KAYLA_VISION_ENABLED=true",
        "KAYLA_CAMERA_DEVICE=0",
        "# Screen vision via a see_screen tool (needs grim on Wayland/wlroots).",
        f"KAYLA_SCREEN_ENABLED={_b(a.screen_enabled)}",
        "KAYLA_SCREEN_MAX_WIDTH=1280",
        "",
        "# Long-term memory (auto-off if no OpenAI key).",
        "KAYLA_MEMORY_ENABLED=true",
        "KAYLA_MEMORY_AUTO_CAPTURE=true",
        "KAYLA_MEMORY_PATH=kayla_memory.json",
        "KAYLA_MEMORY_TOP_K=5",
        "",
        "# Wake word (needs a local Vosk model).",
        f"KAYLA_WAKE_ENABLED={_b(a.wake_enabled)}",
        "KAYLA_WAKE_BACKEND=vosk",
        f"KAYLA_WAKE_VOSK_MODEL_PATH={a.wake_model_path}",
        "KAYLA_WAKE_PHRASES_SLEEP=at ease",
        "KAYLA_WAKE_GREETING=Yeah?",
        "KAYLA_WAKE_FAREWELL=Alright, later.",
        "",
        "# On-screen face.",
        f"KAYLA_FACE_ENABLED={_b(a.face_enabled)}",
        "KAYLA_FACE_AUTOSTART=true",
        "KAYLA_FACE_FULLSCREEN=false",
        "",
        "# Computer control (shell off unless you chose to trust it; tripwire always on).",
        "KAYLA_BROWSER_ENABLED=true",
        f"KAYLA_SHELL_ENABLED={_b(a.shell_enabled)}",
        "KAYLA_SHELL_BLOCK_DANGEROUS=true",
        "KAYLA_KEYBOARD=wtype",
        "",
        "# Robot body (Arduino over USB; blank port = auto-detect).",
        f"KAYLA_BODY_ENABLED={_b(a.body_enabled)}",
        f"KAYLA_BODY_PORT={a.body_port}",
        "KAYLA_BODY_SERVO_PIN=9",
        "",
        "# OpenAI-only extras (text chat + push-to-talk); ignored on a Gemini setup.",
        "KAYLA_OPENAI_MODEL=gpt-5.4-mini",
        "KAYLA_EMBEDDING_MODEL=text-embedding-3-small",
    ]
    return "\n".join(lines) + "\n"


def summary(a: Answers) -> list[str]:
    """Human-readable recap of what will be turned on, for the wizard's closing screen."""
    on = "on"
    off = "off"
    return [
        f"Brain:   Gemini ({'key set' if a.gemini_api_key else 'NO KEY - she will not start'})",
        f"Memory:  {on if a.openai_api_key else off + ' (add an OpenAI key later to enable)'}",
        f"Wake:    {on if a.wake_enabled else off}",
        f"Screen:  {on if a.screen_enabled else off}",
        f"Body:    {on if a.body_enabled else off}",
        f"Face:    {on if a.face_enabled else off}",
        f"Control: browser on, shell {on if a.shell_enabled else off}",
    ]
