"""Drive Kayla's floating orb from the brain process over its local socket.

Streaming commands (mood, speak, look, message) are queued on a background
thread and never block the caller; if the orb window is not running, they are
dropped and the connection retried later, exactly like the face client.
Conversation-critical operations (``ask``, ``move_to``, ``activate``) open
their own short synchronous connection so the brain gets a real answer or a
timeout instead of losing them.
"""

from __future__ import annotations

import json
import queue
import socket
import threading

from kayla.orb.state import energy_for_word


class OrbClient:
    """A brain-side handle for the orb window."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8766) -> None:
        self._addr = (host, port)
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._stream, daemon=True)
        self._thread.start()

    # -- fire-and-forget streaming -----------------------------------------

    def set_mood(self, mood: str) -> None:
        """Energize the orb; classic face moods are accepted too."""
        self._queue.put(f"state {energy_for_word(mood)}")

    def set_speaking(self, speaking: bool) -> None:
        """Turn the equalizer on while she talks."""
        self._queue.put(f"speak {1 if speaking else 0}")

    def look(self, x: float, y: float) -> None:
        """Tilt the sphere toward a point (-1..1)."""
        self._queue.put(f"look {x:.3f} {y:.3f}")

    def message(self, text: str) -> None:
        """Show a one-line status under the orb."""
        self._queue.put("msg " + " ".join(text.splitlines())[:120])

    def close(self) -> None:
        """Stop the sender thread."""
        self._stop.set()
        self._queue.put(None)

    def _stream(self) -> None:
        sock: socket.socket | None = None
        while not self._stop.is_set():
            try:
                command = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if command is None:
                break
            try:
                if sock is None:
                    sock = socket.create_connection(self._addr, timeout=1.0)
                sock.sendall((command + "\n").encode())
            except OSError:
                if sock is not None:
                    sock.close()
                sock = None
        if sock is not None:
            sock.close()

    # -- synchronous one-shot operations ------------------------------------
    @staticmethod
    def _sync(addr: tuple[str, int], lines: list[str], *, expect: int, timeout: float) -> list[str]:
        """Open a short connection, send lines, read exactly ``expect`` replies."""
        try:
            with socket.create_connection(addr, timeout=timeout) as sock:
                sock.settimeout(timeout)
                for line in lines:
                    sock.sendall((line + "\n").encode())
                replies: list[str] = []
                stream = sock.makefile("rb")
                for _index in range(expect):
                    raw = stream.readline()
                    if not raw:
                        break
                    replies.append(raw.decode("utf-8", "replace").strip())
                return replies
        except OSError:
            return []

    def command(self, text: str, timeout: float = 5.0) -> str | None:
        """Send one line, get one line back (or None)."""
        replies = self._sync(self._addr, [text], expect=1, timeout=timeout)
        return replies[0] if replies else None

    def move_to(self, target: str, timeout: float = 5.0) -> bool:
        """Move the window to a named slot ("left") or absolute "x y"."""
        return self.command(f"move {target}", timeout=timeout) == "ok"

    def activate(self) -> bool:
        """Raise the orb window (single-instance activation path)."""
        return self.command("focus", timeout=2.0) == "ok"

    def ping(self, timeout: float = 1.5) -> bool:
        """Liveness check used by launchers for single-instance behavior."""
        return self.command("ping", timeout=timeout) == "pong"

    def ask(self, title: str, options: list[str], timeout: float = 300.0) -> int | None:
        """Show chips and block until an answer, dismissal, or timeout."""
        payload = json.dumps({"title": title, "options": options})
        replies = self._sync(self._addr, [f"ask {payload}"], expect=2, timeout=timeout)
        if len(replies) < 2 or not replies[1].startswith("answer "):
            return None
        try:
            index = int(replies[1].split()[1])
        except (ValueError, IndexError):
            return None
        return index if index >= 0 else None
