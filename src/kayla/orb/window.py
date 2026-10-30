"""Open Kayla's floating orb and connect the brain to it over a socket.

Shared by realtime mode and the wake gate: both need the orb started
(optionally as its own detached process) plus an ``OrbClient`` to drive it.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from kayla.config.settings import Settings


def open_orb_window(settings: Settings) -> tuple[Any, Any]:
    """Open the floating orb (optionally launching its window), or (None, None).

    Returns ``(orb_client, window_process)``; both are ``None`` when the orb is
    disabled. The window starts in its own session, so a terminal closing can
    never take the orb down with it.
    """
    if not settings.orb_enabled:
        return None, None
    from kayla.orb.client import OrbClient

    client = OrbClient(settings.orb_host, settings.orb_port)
    process = None
    if settings.orb_autostart:
        try:
            command = [
                sys.executable,
                "-m",
                "kayla.orb.app",
                "--host",
                settings.orb_host,
                "--port",
                str(settings.orb_port),
                "--width",
                str(settings.orb_window_width),
                "--height",
                str(settings.orb_window_height),
            ]
            # Detached: the orb outlives the shell that started Kayla.
            process = subprocess.Popen(command, start_new_session=True)
            print("Orb: opening the floating window.")
        except Exception as error:  # noqa: BLE001 - the orb is optional; degrade
            print(f"Orb: couldn't open the window ({error}); run 'kayla-orb' yourself.")
    return client, process
