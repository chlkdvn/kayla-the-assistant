"""Offline tests for the CLI front door: popout default, text chat, exit paths."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace as NS

import pytest

from kayla.interfaces import cli

# ------------------------------------------------------------------ text mode


def test_wants_text_mode_flags() -> None:
    assert cli._wants_text_mode(["--chat"]) is True
    assert cli._wants_text_mode(["--text"]) is True
    assert cli._wants_text_mode([]) is False
    assert cli._wants_text_mode(["--orb-width", "420"]) is False


def test_run_chat_loop_answers_and_exits() -> None:
    lines = iter(["hello there", "/exit"])
    written: list[str] = []

    class FakeSession:
        def __init__(self) -> None:
            self.sent: list[str] = []
            self.reset_count = 0

        def send(self, text: str):
            self.sent.append(text)
            return NS(text="Hi, I'm Kayla.")

        def reset(self) -> None:
            self.reset_count += 1

    session = FakeSession()
    cli.run_chat(
        session,  # type: ignore[arg-type]
        robot_name="Kayla",
        read=lambda _prompt: next(lines),
        write=written.append,
    )

    assert session.sent == ["hello there"]
    assert any("Hi, I'm Kayla." in line for line in written)
    assert session.reset_count == 0


def test_run_chat_handles_slash_commands() -> None:
    lines = iter(["/reset", "/help", "/quit"])
    written: list[str] = []

    class FakeSession:
        def __init__(self) -> None:
            self.reset_count = 0
            self.sent: list[str] = []

        def send(self, text: str):
            raise AssertionError("no plain message should be sent")

        def reset(self) -> None:
            self.reset_count += 1

    session = FakeSession()
    cli.run_chat(
        session,  # type: ignore[arg-type]
        robot_name="Kayla",
        read=lambda _prompt: next(lines),
        write=written.append,
    )

    assert session.reset_count == 1
    assert any("/reset starts over" in line for line in written)
    assert any("Goodbye" in line for line in written)


def test_run_chat_survives_provider_errors() -> None:
    lines = iter(["boom", "/exit"])
    written: list[str] = []

    class FakeSession:
        def send(self, text: str):
            raise RuntimeError("the internet is down")

    cli.run_chat(
        FakeSession(),  # type: ignore[arg-type]
        robot_name="Kayla",
        read=lambda _prompt: next(lines),
        write=written.append,
    )

    assert any("could not answer" in line for line in written)


# ------------------------------------------------------------------- popout


class _FakeOrb:
    """Either an awake orb (ping True) or none (ping False)."""

    def __init__(self) -> None:
        self.activated = False
        self.pinged = False

    def ping(self, timeout: float = 1.5) -> bool:  # noqa: ARG002 - signature parity
        self.pinged = True
        return True

    def activate(self) -> bool:
        self.activated = True
        return True


def test_spawn_popout_focusses_an_already_running_orb(monkeypatch) -> None:
    orb = _FakeOrb()

    def fake_client(host: str, port: int):  # noqa: ARG001 - socket never opened
        return orb

    monkeypatch.setattr("kayla.orb.client.OrbClient", fake_client)

    settings = NS(orb_host="127.0.0.1", orb_port=8766)
    message = cli.spawn_popout(settings)

    assert "focused" in message
    assert orb.activated


def test_spawn_popout_starts_a_detached_session(monkeypatch) -> None:
    def fake_client(host: str, port: int):  # noqa: ARG001 - unused fake
        return NS(ping=lambda timeout=1.5: False)

    monkeypatch.setattr("kayla.orb.client.OrbClient", fake_client)
    captured: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        captured["command"] = " ".join(command)
        captured["kwargs"] = kwargs
        return NS(pid=4242)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    settings = NS(orb_host="127.0.0.1", orb_port=8766)
    message = cli.spawn_popout(settings)

    assert "floating up" in message
    assert "kayla.interfaces.realtime_cli" in captured["command"]  # runs the realtime brain
    kwargs = captured["kwargs"]
    assert kwargs["start_new_session"] is True  # detached: survives terminal closing
    assert kwargs["stdout"] is kwargs["stderr"]  # both go to the session log
    kwargs["stdout"].close()  # we opened that handle inside spawn_popout


def test_main_exits_with_setup_message_without_a_key(monkeypatch) -> None:
    import sys

    monkeypatch.setattr(sys, "argv", ["kayla"])

    def boom() -> None:
        raise cli.ConfigurationError("GROQ_API_KEY missing")

    class FakeSettings:
        @staticmethod
        def from_env() -> None:
            boom()

    monkeypatch.setattr(cli, "Settings", FakeSettings)

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 2
