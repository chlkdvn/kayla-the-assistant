"""Load and validate settings without exposing secrets to other concerns."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when Kayla cannot safely start with the supplied configuration."""


_TRUE_WORDS = {"true", "1", "yes", "on"}
_FALSE_WORDS = {"false", "0", "no", "off"}


def _parse_bool(raw: str, name: str) -> bool:
    """Read a forgiving boolean flag, rejecting anything ambiguous."""
    text = raw.strip().lower()
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    raise ConfigurationError(f"{name} must be true or false.")


def _parse_phrase_list(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    """Read a comma-separated list of trigger phrases; empty means none."""
    if raw is None:
        return default
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    """Values required to construct the application."""

    groq_api_key: str
    groq_base_url: str = "https://api.groq.com/openai/v1"
    chat_model: str = "openai/gpt-oss-120b"
    robot_name: str = "Kayla"
    transcription_model: str = "whisper-large-v3-turbo"
    speech_model: str = "canopylabs/orpheus-v1-english"
    speech_voice: str = "hannah"
    microphone_sample_rate: int = 16_000
    audio_input_device: str | None = None
    audio_output_device: str | None = None
    realtime_vad_silence_ms: int = 450
    realtime_half_duplex: bool = True
    realtime_echo_cancel: bool = False
    gemini_api_key: str = ""
    gemini_realtime_model: str = "gemini-3.1-flash-live-preview"
    gemini_voice: str = "Leda"
    gemini_affective_dialog: bool = False
    tone_cues_enabled: bool = True
    wake_enabled: bool = True
    wake_backend: str = "vosk"
    wake_vosk_model_path: str = ""
    wake_phrases_wake: tuple[str, ...] = ()
    wake_phrases_sleep: tuple[str, ...] = ("at ease",)
    wake_access_key: str = ""
    wake_keyword_attention_path: str = ""
    wake_keyword_at_ease_path: str = ""
    wake_sensitivity: float = 0.5
    wake_auto_sleep_seconds: int = 90
    wake_quick_sleep_seconds: int = 30
    wake_greeting: str = "Yeah?"
    wake_farewell: str = "Alright, later."
    vision_enabled: bool = True
    camera_device_index: int = 0
    vision_image_max_width: int = 768
    screen_enabled: bool = True
    screen_max_width: int = 1280
    # Speaker volume trim: multiplies Kayla's output audio before the limiter.
    speaker_gain: float = 0.8
    browser_enabled: bool = True
    shell_enabled: bool = False
    shell_timeout_seconds: int = 20
    shell_block_dangerous: bool = True
    terminal_command: str = ""
    keyboard_tool: str = ""
    face_enabled: bool = False
    face_host: str = "127.0.0.1"
    face_port: int = 8765
    face_autostart: bool = True
    face_fullscreen: bool = True
    face_window_width: int = 480
    face_window_height: int = 320
    orb_enabled: bool = True
    orb_host: str = "127.0.0.1"
    orb_port: int = 8766
    orb_autostart: bool = True
    orb_window_width: int = 420
    orb_window_height: int = 260
    orb_opacity: float = 0.96
    system_tools_enabled: bool = True
    devices_enabled: bool = True
    devices_bridge_port: int = 8711
    devices_path: str = "kayla_devices.json"
    memory_enabled: bool = True
    memory_auto_capture: bool = True
    memory_path: str = "kayla_memory.json"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    memory_top_k: int = 5

    @classmethod
    def from_env(cls) -> Settings:
        """Load a local `.env`, then read settings from the process environment."""
        load_dotenv()
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> Settings:
        """Create settings from a mapping, keeping validation easy to unit test."""
        groq_api_key = values.get("GROQ_API_KEY", "").strip()
        if groq_api_key == "replace-with-your-api-key":
            groq_api_key = ""
        if not groq_api_key:
            raise ConfigurationError(
                "GROQ_API_KEY is missing. Kayla's chat, push-to-talk voice, wake "
                "greetings and memory seeding need a free Groq key - get one at "
                "https://console.groq.com/keys and add it to your .env."
            )
        groq_base_url = values.get("KAYLA_GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()

        model = values.get("KAYLA_CHAT_MODEL", "openai/gpt-oss-120b").strip()
        robot_name = values.get("KAYLA_NAME", "Kayla").strip()
        transcription_model = values.get(
            "KAYLA_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo"
        ).strip()
        speech_model = values.get("KAYLA_SPEECH_MODEL", "canopylabs/orpheus-v1-english").strip()
        speech_voice = values.get("KAYLA_SPEECH_VOICE", "hannah").strip()
        sample_rate_text = values.get("KAYLA_MICROPHONE_SAMPLE_RATE", "16000").strip()
        input_device = values.get("KAYLA_AUDIO_INPUT_DEVICE", "").strip() or None
        output_device = values.get("KAYLA_AUDIO_OUTPUT_DEVICE", "").strip() or None
        realtime_silence_text = values.get("KAYLA_REALTIME_VAD_SILENCE_MS", "450").strip()
        realtime_half_duplex = _parse_bool(
            values.get("KAYLA_REALTIME_HALF_DUPLEX", "true"), "KAYLA_REALTIME_HALF_DUPLEX"
        )
        realtime_echo_cancel = _parse_bool(
            values.get("KAYLA_REALTIME_ECHO_CANCEL", "false"),
            "KAYLA_REALTIME_ECHO_CANCEL",
        )
        gemini_api_key = (
            values.get("GEMINI_API_KEY", "").strip()
            or values.get("KAYLA_GEMINI_API_KEY", "").strip()  # noqa: E501
        )
        gemini_realtime_model = values.get(
            "KAYLA_GEMINI_REALTIME_MODEL", "gemini-3.1-flash-live-preview"
        ).strip()
        gemini_voice = values.get("KAYLA_GEMINI_VOICE", "Leda").strip()
        gemini_affective_dialog = _parse_bool(
            values.get("KAYLA_GEMINI_AFFECTIVE_DIALOG", "false"), "KAYLA_GEMINI_AFFECTIVE_DIALOG"
        )
        tone_cues_enabled = _parse_bool(
            values.get("KAYLA_TONE_CUES_ENABLED", "true"), "KAYLA_TONE_CUES_ENABLED"
        )
        wake_enabled = _parse_bool(values.get("KAYLA_WAKE_ENABLED", "true"), "KAYLA_WAKE_ENABLED")
        wake_backend = values.get("KAYLA_WAKE_BACKEND", "vosk").strip().lower()
        wake_vosk_model_path = values.get("KAYLA_WAKE_VOSK_MODEL_PATH", "").strip()
        wake_phrases_wake = _parse_phrase_list(values.get("KAYLA_WAKE_PHRASES_WAKE"), ())
        wake_phrases_sleep = _parse_phrase_list(
            values.get("KAYLA_WAKE_PHRASES_SLEEP"), ("at ease",)
        )  # noqa: E501
        wake_access_key = values.get("KAYLA_WAKE_ACCESS_KEY", "").strip()
        wake_attention_path = values.get("KAYLA_WAKE_KEYWORD_ATTENTION_PATH", "").strip()
        wake_at_ease_path = values.get("KAYLA_WAKE_KEYWORD_AT_EASE_PATH", "").strip()
        wake_sensitivity_text = values.get("KAYLA_WAKE_SENSITIVITY", "0.5").strip()
        wake_auto_sleep_text = values.get("KAYLA_WAKE_AUTO_SLEEP_SECONDS", "90").strip()
        wake_quick_sleep_text = values.get("KAYLA_WAKE_QUICK_SLEEP_SECONDS", "30").strip()
        wake_greeting = values.get("KAYLA_WAKE_GREETING", "Yeah?")
        wake_farewell = values.get("KAYLA_WAKE_FAREWELL", "Alright, later.")
        vision_enabled = _parse_bool(
            values.get("KAYLA_VISION_ENABLED", "true"), "KAYLA_VISION_ENABLED"
        )  # noqa: E501
        camera_device_text = values.get("KAYLA_CAMERA_DEVICE", "0").strip()
        vision_max_width_text = values.get("KAYLA_VISION_MAX_WIDTH", "768").strip()
        screen_enabled = _parse_bool(
            values.get("KAYLA_SCREEN_ENABLED", "true"), "KAYLA_SCREEN_ENABLED"
        )
        screen_max_width_text = values.get("KAYLA_SCREEN_MAX_WIDTH", "1280").strip()
        speaker_gain_text = values.get("KAYLA_SPEAKER_GAIN", "0.8").strip()
        browser_enabled = _parse_bool(
            values.get("KAYLA_BROWSER_ENABLED", "true"), "KAYLA_BROWSER_ENABLED"
        )
        shell_enabled = _parse_bool(
            values.get("KAYLA_SHELL_ENABLED", "false"), "KAYLA_SHELL_ENABLED"
        )  # noqa: E501
        shell_block_dangerous = _parse_bool(
            values.get("KAYLA_SHELL_BLOCK_DANGEROUS", "true"), "KAYLA_SHELL_BLOCK_DANGEROUS"
        )
        shell_timeout_text = values.get("KAYLA_SHELL_TIMEOUT_SECONDS", "20").strip()
        terminal_command = values.get("KAYLA_TERMINAL", "").strip()
        keyboard_tool = values.get("KAYLA_KEYBOARD", "").strip()
        face_enabled = _parse_bool(values.get("KAYLA_FACE_ENABLED", "false"), "KAYLA_FACE_ENABLED")
        face_host = values.get("KAYLA_FACE_HOST", "127.0.0.1").strip() or "127.0.0.1"
        face_port_text = values.get("KAYLA_FACE_PORT", "8765").strip()
        face_autostart = _parse_bool(
            values.get("KAYLA_FACE_AUTOSTART", "true"), "KAYLA_FACE_AUTOSTART"
        )  # noqa: E501
        face_fullscreen = _parse_bool(
            values.get("KAYLA_FACE_FULLSCREEN", "true"), "KAYLA_FACE_FULLSCREEN"
        )
        face_window_width_text = values.get("KAYLA_FACE_WIDTH", "480").strip()
        face_window_height_text = values.get("KAYLA_FACE_HEIGHT", "320").strip()
        orb_enabled = _parse_bool(values.get("KAYLA_ORB_ENABLED", "true"), "KAYLA_ORB_ENABLED")
        orb_host = values.get("KAYLA_ORB_HOST", "127.0.0.1").strip() or "127.0.0.1"
        orb_port_text = values.get("KAYLA_ORB_PORT", "8766").strip()
        orb_autostart = _parse_bool(
            values.get("KAYLA_ORB_AUTOSTART", "true"), "KAYLA_ORB_AUTOSTART"
        )  # noqa: E501
        orb_window_width_text = values.get("KAYLA_ORB_WIDTH", "420").strip()
        orb_window_height_text = values.get("KAYLA_ORB_HEIGHT", "260").strip()
        orb_opacity_text = values.get("KAYLA_ORB_OPACITY", "0.96").strip()
        system_tools_enabled = _parse_bool(
            values.get("KAYLA_SYSTEM_TOOLS_ENABLED", "true"), "KAYLA_SYSTEM_TOOLS_ENABLED"
        )  # noqa: E501
        devices_enabled = _parse_bool(
            values.get("KAYLA_DEVICES_ENABLED", "true"), "KAYLA_DEVICES_ENABLED"
        )  # noqa: E501
        devices_bridge_port_text = values.get("KAYLA_DEVICES_PORT", "8711").strip()
        devices_path = (
            values.get("KAYLA_DEVICES_PATH", "kayla_devices.json").strip() or "kayla_devices.json"
        )
        memory_enabled = _parse_bool(
            values.get("KAYLA_MEMORY_ENABLED", "true"), "KAYLA_MEMORY_ENABLED"
        )  # noqa: E501
        memory_auto_capture = _parse_bool(
            values.get("KAYLA_MEMORY_AUTO_CAPTURE", "true"), "KAYLA_MEMORY_AUTO_CAPTURE"
        )
        memory_path = values.get("KAYLA_MEMORY_PATH", "kayla_memory.json").strip()
        embedding_model = values.get("KAYLA_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").strip()
        memory_top_k_text = values.get("KAYLA_MEMORY_TOP_K", "5").strip()

        if not model:
            raise ConfigurationError("KAYLA_CHAT_MODEL cannot be empty.")
        if not robot_name:
            raise ConfigurationError("KAYLA_NAME cannot be empty.")
        if not transcription_model:
            raise ConfigurationError("KAYLA_TRANSCRIPTION_MODEL cannot be empty.")
        if not speech_model:
            raise ConfigurationError("KAYLA_SPEECH_MODEL cannot be empty.")
        if not speech_voice:
            raise ConfigurationError("KAYLA_SPEECH_VOICE cannot be empty.")
        if not gemini_realtime_model:
            raise ConfigurationError("KAYLA_GEMINI_REALTIME_MODEL cannot be empty.")
        if not gemini_voice:
            raise ConfigurationError("KAYLA_GEMINI_VOICE cannot be empty.")
        if keyboard_tool and keyboard_tool not in {"xdotool", "ydotool", "wtype"}:
            raise ConfigurationError(
                "KAYLA_KEYBOARD must be xdotool, ydotool, wtype, or empty for auto-detection."
            )

        try:
            face_port = int(face_port_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_FACE_PORT must be an integer.") from error

        try:
            orb_port = int(orb_port_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_ORB_PORT must be an integer.") from error

        try:
            orb_window_width = int(orb_window_width_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_ORB_WIDTH must be an integer.") from error
        if orb_window_width <= 0:
            raise ConfigurationError("KAYLA_ORB_WIDTH must be positive.")

        try:
            orb_window_height = int(orb_window_height_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_ORB_HEIGHT must be an integer.") from error
        if orb_window_height <= 0:
            raise ConfigurationError("KAYLA_ORB_HEIGHT must be positive.")

        try:
            orb_opacity = float(orb_opacity_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_ORB_OPACITY must be a number.") from error
        if not 0.2 <= orb_opacity <= 1.0:
            raise ConfigurationError("KAYLA_ORB_OPACITY must be between 0.2 and 1.0.")

        try:
            devices_bridge_port = int(devices_bridge_port_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_DEVICES_PORT must be an integer.") from error

        try:
            face_window_width = int(face_window_width_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_FACE_WIDTH must be an integer.") from error
        if face_window_width <= 0:
            raise ConfigurationError("KAYLA_FACE_WIDTH must be positive.")

        try:
            face_window_height = int(face_window_height_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_FACE_HEIGHT must be an integer.") from error
        if face_window_height <= 0:
            raise ConfigurationError("KAYLA_FACE_HEIGHT must be positive.")

        try:
            sample_rate = int(sample_rate_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_MICROPHONE_SAMPLE_RATE must be an integer.") from error
        if sample_rate <= 0:
            raise ConfigurationError("KAYLA_MICROPHONE_SAMPLE_RATE must be positive.")

        try:
            realtime_silence_ms = int(realtime_silence_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_REALTIME_VAD_SILENCE_MS must be an integer.") from error
        if realtime_silence_ms <= 0:
            raise ConfigurationError("KAYLA_REALTIME_VAD_SILENCE_MS must be positive.")

        if wake_backend not in {"vosk", "porcupine"}:
            raise ConfigurationError("KAYLA_WAKE_BACKEND must be vosk or porcupine.")

        try:
            wake_sensitivity = float(wake_sensitivity_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_WAKE_SENSITIVITY must be a number.") from error
        if not 0 <= wake_sensitivity <= 1:
            raise ConfigurationError("KAYLA_WAKE_SENSITIVITY must be between 0 and 1.")

        try:
            wake_auto_sleep_seconds = int(wake_auto_sleep_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_WAKE_AUTO_SLEEP_SECONDS must be an integer.") from error
        if wake_auto_sleep_seconds < 0:
            raise ConfigurationError("KAYLA_WAKE_AUTO_SLEEP_SECONDS cannot be negative.")

        try:
            wake_quick_sleep_seconds = int(wake_quick_sleep_text)
        except ValueError as error:
            raise ConfigurationError(
                "KAYLA_WAKE_QUICK_SLEEP_SECONDS must be an integer."
            ) from error  # noqa: E501
        if wake_quick_sleep_seconds < 0:
            raise ConfigurationError("KAYLA_WAKE_QUICK_SLEEP_SECONDS cannot be negative.")

        try:
            camera_device_index = int(camera_device_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_CAMERA_DEVICE must be an integer index.") from error

        try:
            vision_image_max_width = int(vision_max_width_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_VISION_MAX_WIDTH must be an integer.") from error
        if vision_image_max_width <= 0:
            raise ConfigurationError("KAYLA_VISION_MAX_WIDTH must be positive.")

        try:
            screen_max_width = int(screen_max_width_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_SCREEN_MAX_WIDTH must be an integer.") from error
        if screen_max_width <= 0:
            raise ConfigurationError("KAYLA_SCREEN_MAX_WIDTH must be positive.")

        try:
            speaker_gain = float(speaker_gain_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_SPEAKER_GAIN must be a number.") from error
        if not 0.05 <= speaker_gain <= 2.0:
            raise ConfigurationError("KAYLA_SPEAKER_GAIN must be between 0.05 and 2.0.")

        try:
            shell_timeout_seconds = int(shell_timeout_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_SHELL_TIMEOUT_SECONDS must be an integer.") from error
        if shell_timeout_seconds <= 0:
            raise ConfigurationError("KAYLA_SHELL_TIMEOUT_SECONDS must be positive.")

        try:
            memory_top_k = int(memory_top_k_text)
        except ValueError as error:
            raise ConfigurationError("KAYLA_MEMORY_TOP_K must be an integer.") from error
        if memory_top_k <= 0:
            raise ConfigurationError("KAYLA_MEMORY_TOP_K must be positive.")

        return cls(
            groq_api_key=groq_api_key,
            groq_base_url=groq_base_url,
            chat_model=model,
            robot_name=robot_name,
            transcription_model=transcription_model,
            speech_model=speech_model,
            speech_voice=speech_voice,
            microphone_sample_rate=sample_rate,
            audio_input_device=input_device,
            audio_output_device=output_device,
            realtime_vad_silence_ms=realtime_silence_ms,
            realtime_half_duplex=realtime_half_duplex,
            realtime_echo_cancel=realtime_echo_cancel,
            gemini_api_key=gemini_api_key,
            gemini_realtime_model=gemini_realtime_model,
            gemini_voice=gemini_voice,
            gemini_affective_dialog=gemini_affective_dialog,
            tone_cues_enabled=tone_cues_enabled,
            wake_enabled=wake_enabled,
            wake_backend=wake_backend,
            wake_vosk_model_path=wake_vosk_model_path,
            wake_phrases_wake=wake_phrases_wake,
            wake_phrases_sleep=wake_phrases_sleep,
            wake_access_key=wake_access_key,
            wake_keyword_attention_path=wake_attention_path,
            wake_keyword_at_ease_path=wake_at_ease_path,
            wake_sensitivity=wake_sensitivity,
            wake_auto_sleep_seconds=wake_auto_sleep_seconds,
            wake_quick_sleep_seconds=wake_quick_sleep_seconds,
            wake_greeting=wake_greeting,
            wake_farewell=wake_farewell,
            vision_enabled=vision_enabled,
            camera_device_index=camera_device_index,
            vision_image_max_width=vision_image_max_width,
            screen_enabled=screen_enabled,
            screen_max_width=screen_max_width,
            speaker_gain=speaker_gain,
            browser_enabled=browser_enabled,
            shell_enabled=shell_enabled,
            shell_timeout_seconds=shell_timeout_seconds,
            shell_block_dangerous=shell_block_dangerous,
            terminal_command=terminal_command,
            keyboard_tool=keyboard_tool,
            face_enabled=face_enabled,
            face_host=face_host,
            face_port=face_port,
            face_autostart=face_autostart,
            face_fullscreen=face_fullscreen,
            face_window_width=face_window_width,
            face_window_height=face_window_height,
            orb_enabled=orb_enabled,
            orb_host=orb_host,
            orb_port=orb_port,
            orb_autostart=orb_autostart,
            orb_window_width=orb_window_width,
            orb_window_height=orb_window_height,
            orb_opacity=orb_opacity,
            system_tools_enabled=system_tools_enabled,
            devices_enabled=devices_enabled,
            devices_bridge_port=devices_bridge_port,
            devices_path=devices_path,
            memory_enabled=memory_enabled,
            memory_auto_capture=memory_auto_capture,
            memory_path=memory_path,
            embedding_model=embedding_model,
            memory_top_k=memory_top_k,
        )
