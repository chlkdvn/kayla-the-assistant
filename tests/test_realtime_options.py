from kayla.config.settings import Settings
from kayla.prompts.kayla_personality import build_kayla_realtime_instructions
from kayla.realtime.options import RealtimeSessionOptions


def _options(**overrides: str) -> RealtimeSessionOptions:
    settings = Settings.from_mapping({"GROQ_API_KEY": "test-key", **overrides})
    return RealtimeSessionOptions.from_settings(settings)


def test_options_track_the_gemini_silence_timing() -> None:
    options = _options()

    assert options.vad_silence_ms == 450


def test_tool_specs_offer_the_look_tool_when_vision_is_enabled() -> None:
    options = _options(KAYLA_VISION_ENABLED="true")

    assert any(tool["name"] == "look" for tool in options.tool_specs())


def test_tool_specs_always_include_at_least_the_mode_tool() -> None:
    options = _options(
        KAYLA_VISION_ENABLED="false",
        KAYLA_SCREEN_ENABLED="false",
        KAYLA_MEMORY_ENABLED="false",
        KAYLA_BROWSER_ENABLED="false",
        KAYLA_SHELL_ENABLED="false",
        KAYLA_FACE_ENABLED="false",
        KAYLA_SYSTEM_TOOLS_ENABLED="false",
        KAYLA_ORB_ENABLED="false",
        KAYLA_DEVICES_ENABLED="false",
    )

    assert [tool["name"] for tool in options.tool_specs()] == ["set_mode"]


def test_tool_specs_should_default_the_machine_tools_on() -> None:
    # New ownership defaults: laptop control, orb, and phone bridge ship enabled.
    names = {tool["name"] for tool in _options().tool_specs()}

    assert {
        "system_status",
        "open_app",
        "close_window",
        "bring_window",
        "split_screen",
        "focus_mode",
        "performance_mode",
        "move_orb",
        "phone_focus",
    } <= names


def test_tool_specs_gates_system_tools_by_flag() -> None:
    off = _options(KAYLA_SYSTEM_TOOLS_ENABLED="false")

    names = {tool["name"] for tool in off.tool_specs()}

    assert "system_status" not in names
    assert "open_app" not in names
    assert "close_window" not in names
    assert "bring_window" not in names
    assert "split_screen" not in names
    assert "focus_mode" not in names
    assert "performance_mode" not in names


def test_bring_window_tool_promises_last_used_pick() -> None:
    options = _options()
    tool = next(tool for tool in options.tool_specs() if tool["name"] == "bring_window")

    description = tool["description"].lower()
    assert "already-open" in description
    assert "most recently" in description


def test_tool_specs_gates_orb_and_phone_tools_by_flags() -> None:
    off_names = {
        tool["name"]
        for tool in _options(
            KAYLA_ORB_ENABLED="false",
            KAYLA_DEVICES_ENABLED="false",
        ).tool_specs()
    }
    on_names = {
        tool["name"]
        for tool in _options(
            KAYLA_ORB_ENABLED="true",
            KAYLA_DEVICES_ENABLED="true",
        ).tool_specs()
    }

    assert "move_orb" not in off_names
    assert "phone_focus" not in off_names
    assert {"move_orb", "phone_focus"} <= on_names


def test_tool_specs_offer_browser_tools_when_enabled() -> None:
    options = _options(KAYLA_BROWSER_ENABLED="true")

    names = {tool["name"] for tool in options.tool_specs()}

    assert {"open_url", "web_search"} <= names


def test_tool_specs_offer_run_command_only_when_shell_is_enabled() -> None:
    on = _options(KAYLA_SHELL_ENABLED="true")
    off = _options(KAYLA_SHELL_ENABLED="false")

    on_names = {tool["name"] for tool in on.tool_specs()}
    off_names = {tool["name"] for tool in off.tool_specs()}
    assert {
        "run_command",
        "run_in_terminal",
        "type_text",
        "press_key",
        "swipe_desktop",
        "start_type_mode",
    } <= on_names
    assert "run_command" not in off_names
    assert "type_text" not in off_names
    assert "swipe_desktop" not in off_names
    assert "start_type_mode" not in off_names


def test_tool_specs_offer_memory_tools_when_memory_is_enabled() -> None:
    options = _options(KAYLA_MEMORY_ENABLED="true")

    names = {tool["name"] for tool in options.tool_specs()}
    assert {"remember", "recall"} <= names


def test_realtime_prompt_keeps_spoken_responses_short() -> None:
    prompt = build_kayla_realtime_instructions("Nova")

    assert "You are Nova" in prompt
    assert "one to three short" in prompt
    assert "If the user interrupts" in prompt


def test_realtime_instructions_include_the_machine_context() -> None:
    prompt = build_kayla_realtime_instructions("Kayla", environment="MACHINE-FACTS-123")

    assert "MACHINE-FACTS-123" in prompt


def test_realtime_prompt_forces_a_fresh_look_every_time() -> None:
    prompt = build_kayla_realtime_instructions("Kayla").lower()

    assert "blind between looks" in prompt
    assert "fresh frame" in prompt
    assert "do not wait for the user to tell you to look" in prompt


def test_realtime_prompt_maps_spoken_swipes_to_desktop_shortcuts() -> None:
    prompt = build_kayla_realtime_instructions("Kayla")

    assert "swipe left" in prompt.lower()
    assert "Super+Left" in prompt
    assert "Super+Right" in prompt


def test_realtime_prompt_enters_type_mode_without_asking_for_text() -> None:
    prompt = build_kayla_realtime_instructions("Kayla").lower()

    assert '"typing mode"' in prompt
    assert '"type mode"' not in prompt
    assert "start_type_mode" in prompt
    assert "do not ask what to type" in prompt


def test_realtime_prompt_acts_before_speaking_for_one_shot_typing() -> None:
    prompt = build_kayla_realtime_instructions("Kayla").lower()

    assert "direct typing" in prompt
    assert "smart typing" in prompt
    assert "call `type_text` before saying anything" in prompt
    assert "only after the tool result" in prompt


def test_type_text_tool_supports_direct_and_composed_writing() -> None:
    options = _options(KAYLA_SHELL_ENABLED="true")
    tool = next(tool for tool in options.tool_specs() if tool["name"] == "type_text")

    assert "exact words" in tool["description"].lower()
    assert "draft" in tool["description"].lower()
    assert "before speaking" in tool["description"].lower()
