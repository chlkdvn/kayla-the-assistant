"""Open Kayla's floating face window and connect the brain to it over a socket.

Shared by realtime mode and the wake gate: both need the face window started
(optionally launched as its own process) plus a `ScreenFace` client to drive it.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from kayla.config.settings import Settings


def open_face_window(settings: Settings) -> tuple[Any, Any]:
    """Open the on-screen face (optionally launching its window), or (None, None).

    Returns ``(face_client, window_process)``; when the face is disabled both
    are ``None``. The window starts in its own session, so closing Kayla's
    launching terminal never takes her face down with it.
    """
    if not settings.face_enabled:
        return None, None
    from kayla.face.client import ScreenFace

    proc = None
    if settings.face_autostart:
        try:
            command = [
                sys.executable,
                "-m",
                "kayla.face.app",
                "--host",
                settings.face_host,
                "--port",
                str(settings.face_port),
                "--width",
                str(settings.face_window_width),
                "--height",
                str(settings.face_window_height),
            ]
            if settings.face_fullscreen:
                command.append("--fullscreen")
            # `start_new_session` detaches her face from the terminal: the window
            # keeps floating even after the terminal that launched Kayla is gone.
            proc = subprocess.Popen(command, start_new_session=True)
            print("Face: opening the floating window.")
        except Exception as error:  # noqa: BLE001 - the face is optional; degrade gracefully
            print(f"Face: couldn't open the window ({error}); you can run 'kayla-face' yourself.")
    return ScreenFace(settings.face_host, settings.face_port), proc
