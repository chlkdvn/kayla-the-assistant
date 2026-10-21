from kayla.config.settings import Settings


def test_gemini_defaults_need_no_gemini_key_at_load_time() -> None:
    # The Google key is only required when the realtime brain is actually built,
    # so unrelated commands (memory seeding, the face) keep working without it.
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key"})

    assert settings.gemini_api_key == ""
    assert settings.gemini_realtime_model == "gemini-3.1-flash-live-preview"
    assert settings.gemini_voice == "Leda"
    assert settings.gemini_affective_dialog is False


def test_settings_read_their_own_key_model_and_voice() -> None:
    settings = Settings.from_mapping(
        {
            "GROQ_API_KEY": "test-key",
            "GEMINI_API_KEY": "g-key",
            "KAYLA_GEMINI_REALTIME_MODEL": "gemini-live-2.5-flash-preview",
            "KAYLA_GEMINI_VOICE": "Puck",
            "KAYLA_GEMINI_AFFECTIVE_DIALOG": "true",
        }
    )

    assert settings.gemini_api_key == "g-key"
    assert settings.gemini_realtime_model == "gemini-live-2.5-flash-preview"
    assert settings.gemini_voice == "Puck"
    assert settings.gemini_affective_dialog is True


def test_settings_accept_the_kayla_prefixed_gemini_key_alias() -> None:
    settings = Settings.from_mapping(
        {"GROQ_API_KEY": "test-key", "KAYLA_GEMINI_API_KEY": "alias-key"}
    )

    assert settings.gemini_api_key == "alias-key"
