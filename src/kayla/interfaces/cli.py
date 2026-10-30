"""Kayla's front door.

Typing ``kayla`` (in a terminal, the Activities search, anywhere) detaches her
floating orb and voice, then closes the terminal that launched it - Kayla just
hovers over the desktop, no console left behind. An orb that is already
running gets focused, never duplicated. ``kayla --chat`` keeps the classic
typed conversation for debugging.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from kayla.app import build_conversation
from kayla.config.settings import ConfigurationError, Settings
from kayla.conversation.session import ConversationSession
from kayla.system.session_exit import close_calling_terminal

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]

POPLOG_MESSAGE = "Kayla is floating up. Her session log: ~/.cache/kayla/kayla.log"


def run_chat(
    session: ConversationSession,
    *,
    robot_name: str,
    read: InputFunction = input,
    write: OutputFunction = print,
) -> None:
    """Run the interactive terminal loop around an existing conversation session."""
    write(f"{robot_name} is ready. Type /help for commands.")

    while True:
        try:
            user_text = read("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            write(f"\n{robot_name}: Goodbye!")
            return

        if not user_text:
            continue

        command = user_text.casefold()
        if command in {"/exit", "/quit"}:
            write(f"{robot_name}: Goodbye!")
            return
        if command == "/reset":
            session.reset()
            write("Conversation reset. The next message starts a fresh chat.")
            continue
        if command == "/help":
            write("Commands: /reset starts over, /exit closes Kayla.")
            continue

        try:
            reply = session.send(user_text)
        except Exception as error:  # The CLI is the boundary that presents provider failures.
            write(f"{robot_name} could not answer: {error}")
            continue

        write(f"{robot_name}: {reply.text}")


def spawn_popout(settings: Settings) -> str:
    """Start the detached voice+orb session, or focus the orb already floating."""
    from kayla.orb.client import OrbClient

    orb = OrbClient(settings.orb_host, settings.orb_port)
    if orb.ping():
        orb.activate()
        return "Kayla's orb is already up - focused it for you."

    base = _kayla_runtime_cwd()
    log_dir = Path.home() / ".cache" / "kayla"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (log_dir / "kayla.log").open("ab")
    subprocess.Popen(  # noqa: S603 - fixed interpreter, fixed module
        [
            sys.executable,
            "-c",
            "from kayla.interfaces.realtime_cli import main; main()",
        ],
        cwd=str(base) if base is not None else None,
        stdout=log_file,
        stderr=log_file,
        start_new_session=True,
        env={**os.environ, "KAYLA_POP_CANNOT_CLOSE_TERMINAL": "1"},
    )
    return POPLOG_MESSAGE


def _kayla_runtime_cwd() -> Path | None:
    """Prefer ~/.config/kayla as the working base when its .env exists there."""
    home = Path.home() / ".config" / "kayla"
    if (home / ".env").is_file():
        return home
    return None


def _wants_text_mode(argv: list[str]) -> bool:
    return any(flag in {"--chat", "--text"} for flag in argv)


def _run_text_chat() -> None:
    try:
        settings = Settings.from_env()
    except ConfigurationError as error:
        print(f"Setup needed: {error}")
        raise SystemExit(2) from error
    session = build_conversation(settings)
    run_chat(session, robot_name=settings.robot_name)


def main() -> None:
    """Float the orb by default; ``--chat`` keeps her in the terminal."""
    if _wants_text_mode(sys.argv[1:]):
        _run_text_chat()
        return
    try:
        settings = Settings.from_env()
        print(spawn_popout(settings))
    except ConfigurationError as error:
        print(f"Setup needed: {error}")
        raise SystemExit(2) from error
    message = close_calling_terminal()
    if "nothing to close" not in message:
        print(message)


if __name__ == "__main__":
    main()
