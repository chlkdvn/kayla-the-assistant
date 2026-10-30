"""Regression tests for the Gemini Live receive loop and tool handling.

The key behaviour: Gemini's ``session.receive()`` covers a single turn, so the
session must re-open it for every turn. These tests use fake messages and a fake
session so they need no network, key, or audio hardware.
"""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace as NS
from typing import Any

import pytest

from kayla.config.settings import Settings
from kayla.realtime.gemini_session import GeminiVoiceSession
from kayla.realtime.options import RealtimeSessionOptions


class _Stop(Exception):
    """Sentinel used to end the otherwise-infinite receive loop in tests."""


class FakeSpeaker:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def enqueue(self, **_kwargs: Any) -> None: ...
    def interrupt(self) -> None:
        return None

    def is_playing(self) -> bool:
        return False


class FakeFace:
    def __init__(self) -> None:
        self.feelings: list[str] = []

    def set_mood(self, feeling: str) -> None:
        self.feelings.append(feeling)


class FakeLiveSession:
    """Hands out one turn's messages per ``receive()`` call, then stops."""

    def __init__(self, turns: list[list[Any]]) -> None:
        self._turns = list(turns)
        self.tool_responses: list[Any] = []
        self.raw_sends: list[str] = []
        # the live session exposes its websocket as ``_ws``; image tool results are
        # posted straight to it because the SDK can't serialize them itself
        self._ws = NS(send=self._ws_send)

    async def _ws_send(self, data: str) -> None:
        self.raw_sends.append(data)

    def receive(self) -> Any:
        if not self._turns:
            raise _Stop
        turn = self._turns.pop(0)

        async def stream() -> Any:
            for message in turn:
                yield message

        return stream()

    async def send_tool_response(self, *, function_responses: Any) -> None:
        self.tool_responses.append(function_responses)

    async def send_realtime_input(self, **_kwargs: Any) -> None: ...


def _msg(**kwargs: Any) -> Any:
    # a Live message always carries these top-level fields (None when unused)
    base = dict(
        tool_call=None,
        server_content=None,
        data=None,
        session_resumption_update=None,
        go_away=None,
    )
    base.update(kwargs)
    return NS(**base)


def _user(text: str) -> Any:
    content = NS(
        interrupted=False,
        input_transcription=NS(text=text),
        output_transcription=None,
        turn_complete=False,
    )
    return _msg(server_content=content)


def _tool(name: str, args: dict[str, Any], call_id: str = "c1") -> Any:
    return _msg(tool_call=NS(function_calls=[NS(id=call_id, name=name, args=args)]))


def _say(text: str) -> Any:
    content = NS(
        interrupted=False,
        input_transcription=None,
        output_transcription=NS(text=text),
        turn_complete=False,
    )
    return _msg(server_content=content, data=b"\x00\x00")


def _done() -> Any:
    content = NS(
        interrupted=False,
        input_transcription=None,
        output_transcription=None,
        turn_complete=True,
    )
    return _msg(server_content=content)


def _build_session(
    face: FakeFace,
    on_event: Any,
    camera: Any = None,
    screen: Any = None,
    monitor: Any = None,
    apps: Any = None,
    windows: Any = None,
    tiler: Any = None,
    focus_mode: Any = None,
    performance_mode: Any = None,
    devices: Any = None,
) -> GeminiVoiceSession:
    settings = Settings.from_mapping({"GROQ_API_KEY": "x"})
    options = RealtimeSessionOptions.from_settings(settings)
    return GeminiVoiceSession(
        api_key="x",
        model="gemini-3.1-flash-live-preview",
        voice="Leda",
        instructions="be kayla",
        options=options,
        microphone=NS(),
        speaker=FakeSpeaker(),
        on_event=on_event,
        camera=camera,
        screen=screen,
        face=face,
        monitor=monitor,
        apps=apps,
        windows=windows,
        tiler=tiler,
        focus_mode=focus_mode,
        performance_mode=performance_mode,
        devices=devices,
    )


def test_receive_loop_processes_every_turn_not_just_the_first() -> None:
    face = FakeFace()
    events: list[tuple[str, str]] = []
    session = _build_session(face, lambda event: events.append((event.kind, event.text)))
    turn_one = [
        _user("I feel sad"),
        _tool("set_feeling", {"feeling": "sad"}),
        _say("I'm here."),
        _done(),
    ]
    turn_two = [
        _user("thanks"),
        _tool("set_feeling", {"feeling": "happy"}),
        _say("Anytime!"),
        _done(),
    ]
    live = FakeLiveSession([turn_one, turn_two])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    transcripts = [text for kind, text in events if kind == "assistant_transcript"]
    assert transcripts == ["I'm here.", "Anytime!"]  # both turns handled, not just the first
    assert face.feelings == ["sad", "happy"]
    assert len(live.tool_responses) == 2


def test_look_attaches_the_image_inside_the_tool_response_payload() -> None:
    class FakeCamera:
        def capture_jpeg(self) -> bytes:
            return b"FAKEJPEG"

        def close(self) -> None: ...

    face = FakeFace()
    session = _build_session(face, lambda event: None, camera=FakeCamera())
    live = FakeLiveSession([[_tool("look", {}), _say("I see a mug."), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    # An image can't go through send_tool_response (the SDK leaves the bytes raw), so it
    # is posted as a hand-built, base64-encoded wire payload straight to the websocket.
    assert not live.tool_responses  # the normal text path was bypassed
    payload = json.loads(live.raw_sends[0])
    response = payload["toolResponse"]["functionResponses"][0]
    assert response["name"] == "look"
    blob = response["parts"][0]["inlineData"]
    assert blob["mimeType"] == "image/jpeg"
    assert base64.b64decode(blob["data"]) == b"FAKEJPEG"


def test_text_only_tool_results_use_the_normal_send_path() -> None:
    face = FakeFace()
    session = _build_session(face, lambda event: None)
    live = FakeLiveSession([[_tool("set_feeling", {"feeling": "happy"}), _say("Yay!"), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    # No image -> the supported send_tool_response method, no raw socket writes.
    assert not live.raw_sends
    assert live.tool_responses[0][0].name == "set_feeling"


def test_mic_stays_muted_while_speaking_even_after_the_buffer_drains() -> None:
    # Regression: her audio streams in bursts, so mid-sentence the playback buffer empties
    # and is_playing() reads False. If we only muted on is_playing(), the mic would unmute
    # mid-word, feed her own echo back in, and Gemini would cut her off. `_speaking` keeps
    # the mic muted across those gaps.
    face = FakeFace()
    session = _build_session(face, lambda event: None)
    session._speaking = True  # mid-sentence; FakeSpeaker.is_playing() returns False

    class Mic:
        def __init__(self) -> None:
            self.count = 0

        async def read_chunk(self) -> bytes:
            self.count += 1
            if self.count > 4:
                raise _Stop
            return b"\x01\x02"

    class Capturing:
        def __init__(self) -> None:
            self.audio_sends = 0

        async def send_realtime_input(self, **kwargs: Any) -> None:
            if "audio" in kwargs:
                self.audio_sends += 1

    session._microphone = Mic()
    connection = Capturing()
    with pytest.raises(_Stop):
        asyncio.run(session._send_microphone(connection))

    assert connection.audio_sends == 0  # never forwarded the mic while she was speaking


def test_one_bad_message_does_not_end_the_conversation() -> None:
    face = FakeFace()
    events: list[tuple[str, str]] = []
    session = _build_session(face, lambda event: events.append((event.kind, event.text)))
    broken = NS()  # missing attributes -> raises inside _handle_message
    live = FakeLiveSession([[broken, _user("hi"), _say("Hello!"), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    assert any(kind == "error" for kind, _ in events)
    assert ("assistant_transcript", "Hello!") in events  # survived the bad message


class _FakeScreen:
    def __init__(self, jpeg: bytes = b"SCREENSHOT") -> None:
        self._jpeg = jpeg

    def capture_jpeg(self) -> bytes:
        return self._jpeg


def test_see_screen_attaches_a_screenshot_when_a_screen_is_present() -> None:
    session = _build_session(FakeFace(), lambda _event: None, screen=_FakeScreen(b"IMG"))

    text, image = asyncio.run(session._see_screen())

    assert image == b"IMG"  # the screenshot is attached for the model to read
    assert "screen" in text.lower()


def test_see_screen_degrades_cleanly_with_no_screen() -> None:
    session = _build_session(FakeFace(), lambda _event: None)  # no screen configured

    text, image = asyncio.run(session._see_screen())

    assert image is None  # nothing attached
    assert "can't see the screen" in text.lower()  # she says so instead of crashing


def test_quiet_mode_suppresses_audio_until_speak_is_heard() -> None:
    face = FakeFace()
    events: list[tuple[str, str]] = []
    queue: list[bytes] = []

    class FakeSpeaker:
        def start(self) -> None: ...
        def stop(self) -> None: ...
        def enqueue(self, **kwargs: Any) -> None:
            queue.append(kwargs["audio"])

        def interrupt(self) -> None:
            return None

        def is_playing(self) -> bool:
            return False

    session = _build_session(face, lambda event: events.append((event.kind, event.text)), None)
    session._speaker = FakeSpeaker()
    session._mode = "shutup"
    live = FakeLiveSession([[_user("what time is it?"), _say("It is noon."), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    assert queue == []  # her reply was swallowed while she is quiet
    assert not [(kind, text) for kind, text in events if kind == "assistant_transcript"]

    live = FakeLiveSession([[_user("speak"), _say("Back!"), _done()]])
    session._session = live
    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    assert queue == [b"\x00\x00"]  # audio reopened, she speaks again
    assert session._mode == "speak"


# --------------------------------------------------- laptop-awareness handlers


class FakeMonitor:
    def __init__(self) -> None:
        self.described = 0

    def describe(self) -> str:
        self.described += 1
        return "RAM 5.2GB; CPU 12%; battery 80%; chromium + code open"


class FakeApps:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def open(self, query: str) -> str:
        self.opened.append(query)
        return f"Opening {query}."


class FakeWindows:
    def __init__(self) -> None:
        self.closed: list[str] = []

    def close(self, target: str) -> str:
        self.closed.append(target)
        return f"Closed 1 window ({target})."


class FakeTiler:
    def __init__(self) -> None:
        self.slots: list[int] = []

    def split(self, count: int) -> str:
        self.slots.append(count)
        return f"Tiled into {count} slots."


class FakeFocus:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def on(self) -> str:
        self.calls.append("on")
        return "Notifications off."

    def off(self) -> str:
        self.calls.append("off")
        return "Notifications back on."


class FakePower:
    def __init__(self) -> None:
        self.profiles: list[str] = []

    def set(self, profile: str) -> str:
        self.profiles.append(profile)
        return f"Power profile: {profile}."


class FakeBridge:
    def __init__(self) -> None:
        self.attached: list[dict[str, str]] = []

    def devices(self) -> list[Any]:
        return [NS(name="Divine's iPhone")]

    def attach(self, action: dict[str, str]) -> str:
        self.attached.append(action)
        return "cmd-7"


class FakeMovableFace:
    def __init__(self) -> None:
        self.spots: list[str] = []

    def set_mood(self, feeling: str) -> None: ...  # ignore mood calls here

    def move_to(self, label: str) -> bool:
        self.spots.append(label)
        return True


def test_system_status_runs_inside_a_live_turn() -> None:
    monitor = FakeMonitor()
    face = FakeFace()
    session = _build_session(face, lambda _e: None, monitor=monitor)
    live = FakeLiveSession([[_tool("system_status", {}), _say("Busy?"), _done()]])
    session._session = live

    with pytest.raises(_Stop):
        asyncio.run(session._receive_events(live))

    assert monitor.described == 1
    entry = live.tool_responses[0][0]
    assert entry.name == "system_status"
    assert "RAM 5.2GB" in entry.response["result"]  # the model reads the real numbers


def test_open_app_and_close_window_handlers() -> None:
    apps, windows = FakeApps(), FakeWindows()
    session = _build_session(FakeFace(), lambda _e: None, apps=apps, windows=windows)

    opened = asyncio.run(session._open_app("spotify"))
    closed = asyncio.run(session._close_window("chrome"))

    assert apps.opened == ["spotify"]
    assert "Opening" in opened
    assert windows.closed == ["chrome"]
    assert "Closed" in closed


def test_split_screen_passes_the_count() -> None:
    tiler = FakeTiler()
    session = _build_session(FakeFace(), lambda _e: None, tiler=tiler)

    text = asyncio.run(session._split_screen("4"))

    assert tiler.slots == [4]
    assert "4" in text


def test_focus_and_power_handlers_actuate_the_laptop() -> None:
    focus, power = FakeFocus(), FakePower()
    session = _build_session(FakeFace(), lambda _e: None, focus_mode=focus, performance_mode=power)

    on_text = asyncio.run(session._apply_focus_mode("on"))
    off_text = asyncio.run(session._apply_focus_mode("off"))
    power_text = asyncio.run(session._apply_performance_mode("performance"))

    assert focus.calls == ["on", "off"]
    assert "Notifications" in on_text and "back on" in off_text
    assert power.profiles == ["performance"]
    assert "performance" in power_text


def test_handlers_degrade_when_the_tool_is_not_provided() -> None:
    session = _build_session(FakeFace(), lambda _e: None)

    assert asyncio.run(session._system_status()) == "Computer monitoring is turned off."
    assert asyncio.run(session._open_app("spotify")) == "Opening apps is turned off."
    assert asyncio.run(session._split_screen("4")) == "Screen splitting is turned off."
    assert asyncio.run(session._apply_focus_mode("on")) == "Focus control is turned off."
    assert (
        asyncio.run(session._apply_performance_mode("power-saver"))
        == "Power profiles are turned off."
    )
    assert asyncio.run(session._close_window("chrome")) == "Closing windows is turned off."
    assert asyncio.run(session._phone_focus("on")) == "The phone bridge is turned off."


def test_move_orb_instructs_the_client() -> None:
    face = FakeMovableFace()
    session = _build_session(face, lambda _e: None)

    text = asyncio.run(session._move_orb("left"))

    assert face.spots == ["left"]
    assert "Moved to left" in text


def test_move_orb_needs_a_running_window() -> None:
    session = _build_session(FakeFace(), lambda _e: None)  # FakeFace has no move_to

    text = asyncio.run(session._move_orb("left"))

    assert "isn't connected" in text


def test_phone_focus_queues_the_command_and_admits_the_delay() -> None:
    bridge = FakeBridge()
    session = _build_session(FakeFace(), lambda _e: None, devices=bridge)

    text = asyncio.run(session._phone_focus("on"))

    assert bridge.attached == [{"action": "focus_on"}]
    assert "next" in text.lower()  # honest about when the phone applies it


def test_phone_focus_without_devices_says_so() -> None:
    class EmptyBridge:
        def devices(self) -> list[Any]:
            return []

    session = _build_session(FakeFace(), lambda _e: None, devices=EmptyBridge())

    text = asyncio.run(session._phone_focus("on"))

    assert "No phone is paired" in text


def test_quiet_mode_sets_the_orb_to_sleeping() -> None:
    face = FakeFace()
    session = _build_session(face, lambda _e: None)

    session._set_mode("shutup")
    session._set_mode("speak")

    assert face.feelings == ["sleeping", "listening"]


# ------------------------------------------------------- startup chip question


class FakeChipFace:
    """An orb client stand-in: blocks in ask(), records the shown message."""

    def __init__(self, answer: int | None) -> None:
        self._answer = answer
        self.titles: list[str] = []
        self.messages: list[str] = []

    def ask(self, title: str, options: list[str], timeout: float = 300.0) -> int | None:
        self.titles.append(title)
        self._options = options
        return self._answer

    def message(self, text: str) -> None:
        self.messages.append(text)

    def set_mood(self, feeling: str) -> None: ...


def test_startup_chips_actuate_only_the_chosen_action() -> None:
    face = FakeChipFace(answer=1)  # "Focus mode"
    focus, power = FakeFocus(), FakePower()
    session = _build_session(face, lambda _e: None, focus_mode=focus, performance_mode=power)

    asyncio.run(session._startup_question(None))

    assert focus.calls == ["on"]  # notifications silenced
    assert power.profiles == []  # performance was NOT touched
    assert any("Notifications" in message for message in face.messages)


def test_startup_chips_dismissed_actuates_nothing() -> None:
    face = FakeChipFace(answer=None)
    focus, power = FakeFocus(), FakePower()
    session = _build_session(face, lambda _e: None, focus_mode=focus, performance_mode=power)

    asyncio.run(session._startup_question(None))

    assert focus.calls == []
    assert power.profiles == []
    assert face.messages == []


def test_startup_chips_run_only_once_per_session() -> None:
    face = FakeChipFace(answer=3)
    session = _build_session(face, lambda _e: None, focus_mode=FakeFocus())

    asyncio.run(session._startup_question(None))
    asyncio.run(session._startup_question(None))  # no reconnect happened between these

    assert len(face.titles) == 1  # never asks the same start question twice
