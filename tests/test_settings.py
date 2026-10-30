import pytest

from kayla.config.settings import ConfigurationError, Settings


def test_settings_require_a_groq_key() -> None:
    with pytest.raises(ConfigurationError, match="GROQ_API_KEY"):
        Settings.from_mapping({})


def test_settings_read_values_and_defaults() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.groq_api_key == "test-key"
    assert settings.groq_base_url == "https://api.groq.com/openai/v1"
    assert settings.chat_model == "openai/gpt-oss-120b"
    assert settings.robot_name == "Kayla"
    assert settings.transcription_model == "whisper-large-v3-turbo"
    assert settings.speech_model == "canopylabs/orpheus-v1-english"
    assert settings.speech_voice == "hannah"
    assert settings.microphone_sample_rate == 16_000
    assert settings.realtime_vad_silence_ms == 450


def test_settings_reject_the_example_placeholder() -> None:
    with pytest.raises(ConfigurationError, match="GROQ_API_KEY"):
        Settings.from_mapping({"GROQ_API_KEY": "replace-with-your-api-key"})


def test_settings_reject_an_invalid_sample_rate() -> None:
    with pytest.raises(ConfigurationError, match="SAMPLE_RATE"):
        Settings.from_mapping(
            {
                "GROQ_API_KEY": "test-key",
                "KAYLA_MICROPHONE_SAMPLE_RATE": "fast",
            }
        )


def test_settings_reject_an_invalid_vad_silence() -> None:
    with pytest.raises(ConfigurationError, match="VAD_SILENCE_MS"):
        Settings.from_mapping(
            {
                "GROQ_API_KEY": "test-key",
                "KAYLA_REALTIME_VAD_SILENCE_MS": "soon",
            }
        )


def test_settings_wake_defaults() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.wake_enabled is True
    assert settings.wake_backend == "vosk"
    assert settings.wake_vosk_model_path == ""
    assert settings.wake_access_key == ""
    assert settings.wake_keyword_attention_path == ""
    assert settings.wake_keyword_at_ease_path == ""
    assert settings.wake_sensitivity == 0.5
    assert settings.wake_auto_sleep_seconds == 90
    assert settings.wake_quick_sleep_seconds == 30
    assert settings.wake_greeting == "Yeah?"
    assert settings.wake_farewell == "Alright, later."


def test_settings_wake_phrase_defaults() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.wake_phrases_wake == ()  # the name alone wakes her
    assert settings.wake_phrases_sleep == ("at ease",)


def test_settings_reject_a_negative_quick_sleep() -> None:
    with pytest.raises(ConfigurationError, match="QUICK_SLEEP"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_QUICK_SLEEP_SECONDS": "-1"})


def test_settings_wake_phrases_parse_comma_separated_lists() -> None:
    settings = Settings.from_mapping(
        {
            "GROQ_API_KEY": "test-key",
            "KAYLA_WAKE_PHRASES_WAKE": "Hey there, you up ",
            "KAYLA_WAKE_PHRASES_SLEEP": "bye",
        }
    )

    assert settings.wake_phrases_wake == ("hey there", "you up")
    assert settings.wake_phrases_sleep == ("bye",)


def test_settings_empty_wake_phrases_means_name_only() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_PHRASES_WAKE": ""})

    assert settings.wake_phrases_wake == ()


def test_settings_wake_backend_can_be_porcupine() -> None:
    settings = Settings.from_mapping(
        {"GROQ_API_KEY": "test-key", "KAYLA_WAKE_BACKEND": "porcupine"}
    )

    assert settings.wake_backend == "porcupine"


def test_settings_reject_an_unknown_wake_backend() -> None:
    with pytest.raises(ConfigurationError, match="WAKE_BACKEND"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_BACKEND": "magic"})


def test_settings_system_defaults() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.browser_enabled is True
    assert settings.shell_enabled is False  # off until explicitly enabled
    assert settings.shell_timeout_seconds == 20
    assert settings.shell_block_dangerous is True
    assert settings.terminal_command == ""  # empty = auto-detect
    assert settings.keyboard_tool == ""  # empty = auto-detect


def test_settings_shell_can_be_enabled() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_SHELL_ENABLED": "true"})

    assert settings.shell_enabled is True


def test_settings_accepts_a_keyboard_tool_override() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_KEYBOARD": "wtype"})

    assert settings.keyboard_tool == "wtype"


def test_settings_rejects_an_unknown_keyboard_tool() -> None:
    with pytest.raises(ConfigurationError, match="KAYLA_KEYBOARD"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_KEYBOARD": "typewriter"})


def test_settings_dangerous_block_can_be_turned_off() -> None:
    settings = Settings.from_mapping(
        {"GROQ_API_KEY": "test-key", "KAYLA_SHELL_BLOCK_DANGEROUS": "false"}
    )

    assert settings.shell_block_dangerous is False


def test_settings_memory_defaults() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.memory_enabled is True
    assert settings.memory_auto_capture is True
    assert settings.memory_path == "kayla_memory.json"
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.memory_top_k == 5


def test_settings_memory_can_be_disabled() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_MEMORY_ENABLED": "false"})

    assert settings.memory_enabled is False


def test_settings_reject_a_non_positive_memory_top_k() -> None:
    with pytest.raises(ConfigurationError, match="MEMORY_TOP_K"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_MEMORY_TOP_K": "0"})


def test_settings_vision_defaults() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.vision_enabled is True
    assert settings.camera_device_index == 0
    assert settings.vision_image_max_width == 768


def test_settings_vision_can_be_disabled() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_VISION_ENABLED": "false"})

    assert settings.vision_enabled is False


def test_settings_screen_vision_defaults_on() -> None:
    # "Can you see my screen?" should just work; she reads the desktop on ask.
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.screen_enabled is True


def test_settings_screen_vision_can_be_disabled() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_SCREEN_ENABLED": "false"})

    assert settings.screen_enabled is False


def test_settings_speaker_gain_defaults_to_trimmed() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.speaker_gain == pytest.approx(0.8)


def test_settings_speaker_gain_can_be_overridden() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_SPEAKER_GAIN": "1.5"})

    assert settings.speaker_gain == pytest.approx(1.5)


def test_settings_reject_an_unusable_speaker_gain() -> None:
    for env in ({"KAYLA_SPEAKER_GAIN": "loud"}, {"KAYLA_SPEAKER_GAIN": "0.01"}):
        with pytest.raises(ConfigurationError, match="SPEAKER_GAIN"):
            Settings.from_mapping({"GROQ_API_KEY": "test-key", **env})


def test_settings_reject_a_non_integer_camera_device() -> None:
    with pytest.raises(ConfigurationError, match="CAMERA_DEVICE"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_CAMERA_DEVICE": "front"})


def test_settings_realtime_half_duplex_defaults_on() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.realtime_half_duplex is True


def test_settings_realtime_half_duplex_can_be_disabled() -> None:
    settings = Settings.from_mapping(
        {"GROQ_API_KEY": "test-key", "KAYLA_REALTIME_HALF_DUPLEX": "false"}
    )

    assert settings.realtime_half_duplex is False


def test_settings_realtime_echo_cancel_defaults_off() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.realtime_echo_cancel is False


def test_settings_realtime_echo_cancel_can_be_enabled() -> None:
    settings = Settings.from_mapping(
        {"GROQ_API_KEY": "test-key", "KAYLA_REALTIME_ECHO_CANCEL": "true"}
    )

    assert settings.realtime_echo_cancel is True


def test_settings_wake_can_be_disabled() -> None:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_ENABLED": "false"})

    assert settings.wake_enabled is False


def test_settings_reject_an_unparsable_wake_enabled() -> None:
    with pytest.raises(ConfigurationError, match="WAKE_ENABLED"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_ENABLED": "maybe"})


def test_settings_reject_an_out_of_range_wake_sensitivity() -> None:
    with pytest.raises(ConfigurationError, match="WAKE_SENSITIVITY"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_SENSITIVITY": "2"})


def test_settings_reject_a_negative_auto_sleep() -> None:
    with pytest.raises(ConfigurationError, match="AUTO_SLEEP"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_AUTO_SLEEP_SECONDS": "-5"})


def test_settings_reject_an_unparsable_auto_sleep() -> None:
    with pytest.raises(ConfigurationError, match="AUTO_SLEEP"):
        Settings.from_mapping({"GROQ_API_KEY": "test-key", "KAYLA_WAKE_AUTO_SLEEP_SECONDS": "soon"})


def test_settings_laptop_control_defaults_all_on() -> None:
    # New ownership: laptop awareness, the floating orb, and the phone bridge
    # are the product's heart, so they default on.
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.system_tools_enabled is True
    assert settings.orb_enabled is True
    assert settings.orb_host == "127.0.0.1"
    assert settings.orb_port == 8766
    assert settings.orb_autostart is True
    assert settings.orb_window_width == 420
    assert settings.orb_window_height == 260
    assert settings.orb_opacity == pytest.approx(0.96)
    assert settings.devices_enabled is True
    assert settings.devices_bridge_port == 8711
    assert settings.devices_path == "kayla_devices.json"


def test_settings_laptop_control_flags_can_be_disabled() -> None:
    settings = Settings.from_mapping(
        {
            "GROQ_API_KEY": "test-key",
            "KAYLA_SYSTEM_TOOLS_ENABLED": "false",
            "KAYLA_ORB_ENABLED": "false",
            "KAYLA_DEVICES_ENABLED": "false",
        }
    )

    assert settings.system_tools_enabled is False
    assert settings.orb_enabled is False
    assert settings.devices_enabled is False


def test_settings_orb_values_can_be_overridden() -> None:
    settings = Settings.from_mapping(
        {
            "GROQ_API_KEY": "test-key",
            "KAYLA_ORB_PORT": "9001",
            "KAYLA_ORB_WIDTH": "300",
            "KAYLA_ORB_HEIGHT": "180",
            "KAYLA_ORB_OPACITY": "0.5",
            "KAYLA_DEVICES_PORT": "9002",
            "KAYLA_DEVICES_PATH": "phones.json",
        }
    )

    assert settings.orb_port == 9001
    assert settings.orb_window_width == 300
    assert settings.orb_window_height == 180
    assert settings.orb_opacity == pytest.approx(0.5)
    assert settings.devices_bridge_port == 9002
    assert settings.devices_path == "phones.json"


def test_settings_reject_bad_orb_numbers() -> None:
    for env, match in (
        ({"KAYLA_ORB_PORT": "orb"}, "ORB_PORT"),
        ({"KAYLA_ORB_WIDTH": "-3"}, "ORB_WIDTH"),
        ({"KAYLA_ORB_HEIGHT": "zero"}, "ORB_HEIGHT"),
        ({"KAYLA_ORB_OPACITY": "mist"}, "ORB_OPACITY"),
        ({"KAYLA_ORB_OPACITY": "0.1"}, "ORB_OPACITY"),  # below the 0.2 floor
        ({"KAYLA_DEVICES_PORT": "wifi"}, "DEVICES_PORT"),
    ):
        with pytest.raises(ConfigurationError, match=match):
            Settings.from_mapping({"GROQ_API_KEY": "test-key", **env})
