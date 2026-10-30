"""Start Kayla by herself when the PC boots, and make her findable anywhere.

Two installers, both aimed at the user session (no root needed):

1. A systemd **user** service (``kayla.service``) that runs the realtime voice
   session whenever the graphical session starts - so her orb is already
   floating when you log in.
2. A desktop entry (``kayla.desktop``) so typing "kayla" in the GNOME
   Activities search shows her app; launching it opens - or focuses - the orb
   exactly like typing ``kayla`` in a terminal does.

    uv run kayla-boot --install    # set both up
    uv run kayla-boot --remove     # undo both
    uv run kayla-boot --status     # show what is installed

Enabling uses ``systemctl --user``; when systemctl is unavailable the installer
writes the files anyway and prints the single command to run by hand.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "kayla.service"
DESKTOP_NAME = "kayla.desktop"

SERVICE_PATH = Path.home() / ".config" / "systemd" / "user" / SERVICE_NAME
DESKTOP_PATH = Path.home() / ".local" / "share" / "applications" / DESKTOP_NAME
# Paths above are the real defaults for the shell; install()/remove()/status()
# re-derive them from an (optional) ``home`` so tests can use a temp directory.


def _runtime_cwd(home: Path | None = None) -> Path | None:
    base = (home or Path.home()) / ".config" / "kayla"
    return base if (base / ".env").is_file() else None


def _working_directory_line(home: Path | None = None) -> str:
    cwd = _runtime_cwd(home)
    return f"WorkingDirectory={cwd}\n" if cwd is not None else ""


def service_unit(home: Path | None = None) -> str:
    """The systemd user unit contents for this machine's interpreter."""
    python = sys.executable
    directory = _working_directory_line(home)
    return f"""[Unit]
Description=Kayla voice assistant (floating orb + realtime voice)
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
{directory}Environment=KAYLA_BOOT=1
ExecStart={python} -c "from kayla.interfaces.realtime_cli import main; main()"
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
"""


def desktop_entry() -> str:
    """The launcher-shown desktop entry (search "kayla", click to raise)."""
    python = sys.executable
    return f"""[Desktop Entry]
Type=Application
Name=Kayla
Comment=Your floating AI assistant orb
Exec={python} -m kayla.interfaces.cli
Terminal=false
Categories=Utility;
"""


def install(*, run=None, home: Path | None = None) -> str:
    """Write both files and enable the boot service. Reports every step."""
    command = run or _system_ctl
    base = home or Path.home()
    messages: list[str] = []
    for path, contents in (
        (base / ".config" / "systemd" / "user" / SERVICE_NAME, service_unit(home)),
        (base / ".local" / "share" / "applications" / DESKTOP_NAME, desktop_entry()),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        messages.append(f"Wrote {path}")
    if command is not None:
        for argv in (["systemctl", "--user", "daemon-reload"],):
            code, output = command(argv)
            if code != 0:
                messages.append(f"systemctl daemon-reload failed: {output.strip()}")
        code, output = command(["systemctl", "--user", "enable", "--now", SERVICE_NAME])
        if code != 0:
            hand = f"systemctl --user enable --now {SERVICE_NAME}"
            messages.append(f"Enable it by hand: {hand} ({output.strip()})")
        else:
            messages.append("Boot service enabled: Kayla runs when the PC starts.")
    return "\n".join(messages)


def remove(*, run=None, home: Path | None = None) -> str:
    command = run or _system_ctl
    base = home or Path.home()
    messages: list[str] = []
    if command is not None:
        code, output = command(["systemctl", "--user", "disable", "--now", SERVICE_NAME])
        if code != 0 and "not found" not in output.lower():
            messages.append(f"systemctl disable failed: {output.strip()}")
        else:
            messages.append("Boot service disabled.")
    for path in (
        base / ".config" / "systemd" / "user" / SERVICE_NAME,
        base / ".local" / "share" / "applications" / DESKTOP_NAME,
    ):
        if path.exists():
            path.unlink()
            messages.append(f"Removed {path}")
    return "\n".join(messages)


def status(home: Path | None = None) -> str:
    base = home or Path.home()
    lines = [
        "boot service unit: "
        + (
            "installed"
            if (base / ".config" / "systemd" / "user" / SERVICE_NAME).exists()
            else "not installed"
        ),
        "desktop entry:     "
        + (
            "installed"
            if (base / ".local" / "share" / "applications" / DESKTOP_NAME).exists()
            else "not installed"
        ),
    ]
    return "\n".join(lines)


def _system_ctl(argv: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)
    return result.returncode, result.stdout + result.stderr


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Boot-time autostart for Kayla.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="install service + entry")
    group.add_argument("--remove", action="store_true", help="uninstall both")
    group.add_argument("--status", action="store_true", help="show what is installed")
    args = parser.parse_args(argv)
    if args.install:
        print(install())
    elif args.remove:
        print(remove())
    else:
        print(status())


if __name__ == "__main__":
    main()
