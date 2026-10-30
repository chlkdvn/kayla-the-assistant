"""A tiny LAN server so a paired phone can fetch Kayla's focus commands.

Apple does not let another computer switch an iPhone's Focus mode over the
network - there is no public API - so this bridge ships the *demand* side: you
install one Apple Shortcut on the phone (recipe in ``docs/devices.md``) which
pairs with Kayla once, then polls ``GET /commands`` on the same Wi-Fi. Kayla
queues commands here ("put my phone in focus"), your shortcut fetches them and
performs them with its own 'Set Focus' actions, and acknowledges back.

Endpoints (all https-agnostic, plain HTTP, LAN only):

- ``GET /health``                      -> ``{"ok": true, "name": "Kayla"}``
- ``GET /pair?code=NN&name=iPhone``    -> ``{"token": "..."}`` (one-time)
- ``GET /commands?token=T``            -> pending commands, drained
- ``POST /ack?token=T&id=C``           -> mark a command done
- ``POST /notify?token=T&text=...``    -> the phone can send a one-line note

The registry and queue persist to a small JSON file so a restart keeps devices.
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MAX_BODY_BYTES = 8_192

REGISTRY_VERSION = 1


@dataclass(frozen=True)
class PairedDevice:
    """One phone that completed pairing."""

    token: str
    name: str
    last_seen: str


@dataclass
class _Registry:
    """The persisted JSON document behind :class:`DeviceBridge`."""

    version: int = REGISTRY_VERSION
    pair_code: str | None = None
    devices: list[dict[str, str]] = field(default_factory=list)
    pending: list[dict[str, str]] = field(default_factory=list)
    notes: list[dict[str, str]] = field(default_factory=list)


BridgeRouteTable = dict[str, Callable[[], object]]


class DeviceBridge:
    """Pair phones and hand them Kayla's queued commands."""

    def __init__(self, path: Path | None = None, *, robot_name: str = "Kayla") -> None:
        self.path = path
        self.robot_name = robot_name
        self._lock = threading.Lock()
        self._doc = _Registry()
        if path is not None:
            self._load()

    # -- persistence --------------------------------------------------

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            self._doc = _Registry(
                version=int(data.get("version", REGISTRY_VERSION)),
                pair_code=data.get("pair_code"),
                devices=list(data.get("devices", [])),
                pending=list(data.get("pending", [])),
                notes=list(data.get("notes", [])),
            )

    def _save(self) -> None:
        if self.path is None:
            return
        lock_path = self.path.with_suffix(".lock")
        text = json.dumps(asdict(self._doc), indent=2)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic-ish write: temp file next to the target, then replace.
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.path)
        lock_path.touch(exist_ok=True)

    # -- pairing ------------------------------------------------------

    def pair_code(self) -> str:
        """The six-digit code displayed in the orb window (issued on demand)."""
        with self._lock:
            code = self._doc.pair_code
            if not code:
                code = f"{secrets.randbelow(1_000_000):06d}"
                self._doc.pair_code = code
                self._save()
            return code

    def pair(self, code: str, name: str) -> str | None:
        """Exchange a valid pair code for a long-lived device token."""
        with self._lock:
            if code.strip() != (self._doc.pair_code or ""):
                return None
            name = (name.strip() or "iPhone")[:48]
            token = "kayla-" + secrets.token_hex(10)
            self._doc.devices.append({"token": token, "name": name, "last_seen": _now()})
            self._doc.pair_code = None  # one shot: a fresh code comes next time
            self._save()
            return token

    # -- commands -----------------------------------------------------

    def attach(self, action: dict[str, str], *, token: str = "*") -> str:
        """Queue one command for every device (``*``) or one specific token."""
        command = {"id": "c" + secrets.token_hex(4), "token": token}
        command.update(action)
        with self._lock:
            self._doc.pending.append(command)
            self._save()
        return command["id"]

    def drain(self, token: str) -> list[dict[str, str]]:
        """Pop every pending command for a device token (broadcast included)."""
        with self._lock:
            if not self._device(token):
                return []
            self._touch(token)
            mine = [c for c in self._doc.pending if c.get("token") in {token, "*"}]
            self._doc.pending = [c for c in self._doc.pending if c not in mine]
            self._save()
            return [{k: v for k, v in entry.items() if k != "token"} for entry in mine]

    def ack(self, token: str, command_id: str, ok: bool) -> bool:
        """Confirm one fetched command was handled on the phone."""
        with self._lock:
            if self._device(token) is None:
                return False
            self._touch(token)
            note = {"id": command_id, "ok": "1" if ok else "0", "at": _now()}
            self._doc.notes.append(note)
            self._doc.notes = self._doc.notes[-32:]
            self._save()
            return True

    def note(self, token: str, text: str) -> bool:
        """A one-line text message from the paired phone."""
        with self._lock:
            device = self._device(token)
            if device is None or not text:
                return False
            self._touch(token)
            self._doc.notes.append(
                {"id": "n" + secrets.token_hex(3), "text": text[:200], "at": _now()}
            )
            self._doc.notes = self._doc.notes[-32:]
            self._save()
            return True

    def notes(self) -> list[dict[str, str]]:
        """Recent phone messages for the session to surface to Kayla."""
        with self._lock:
            return list(self._doc.notes)

    def devices(self) -> list[PairedDevice]:
        """Paired devices for display and diagnostics."""
        with self._lock:
            return [
                PairedDevice(
                    token=item["token"],
                    name=item.get("name", "device"),
                    last_seen=item.get("last_seen", ""),
                )
                for item in self._doc.devices
            ]

    # -- registry internals -------------------------------------------

    def _device(self, token: str) -> dict[str, str] | None:
        return next((item for item in self._doc.devices if item["token"] == token), None)

    def _touch(self, token: str) -> None:
        device = self._device(token)
        if device is not None:
            device["last_seen"] = _now()


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")


class _BridgeHandler(BaseHTTPRequestHandler):
    """One HTTP request = one registry interaction. LAN-friendly and quiet."""

    timeout = 15

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        self._route("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        self._route("POST")

    def _route(self, method: str) -> None:
        bridge: DeviceBridge = self.server.registry  # type: ignore[attr-defined]
        url = urlparse(self.path)
        path = url.path.strip("/")
        params = {key: values[0] for key, values in parse_qs(url.query).items()}
        body = {}
        if method == "POST":
            raw = self.rfile.read(min(int(self.headers.get("Content-Length", "0")), MAX_BODY_BYTES))
            if raw:
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = {}
        table: BridgeRouteTable = {
            "health": lambda: {"ok": True, "name": bridge.robot_name},
            "pair": lambda: self._pair(params, bridge),
            "commands": lambda: {"commands": bridge.drain(params.get("token", ""))},
            "ack": lambda: {
                "ok": bridge.ack(
                    params.get("token", ""), params.get("id", ""), params.get("ok", "1") != "0"
                )
            },
            "notify": lambda: {
                "ok": bridge.note(params.get("token", ""), str(body.get("text", "")))
            },
        }
        handler = table.get(path)
        if handler is None:
            self._respond(404, {"error": "unknown path", "paths": sorted(table)})
            return
        try:
            self._respond(200, handler())
        except Exception as error:  # noqa: BLE001 - errors shrink to JSON
            self._respond(500, {"error": str(error)})

    def _pair(self, params: dict[str, str], bridge: DeviceBridge) -> object:
        token = bridge.pair(params.get("code", ""), params.get("name", "iPhone"))
        if token is None:
            return {"error": "wrong pairing code", "ok": False}
        return {"ok": True, "token": token}

    def _respond(self, status: int, message: object) -> None:
        payload = json.dumps(message).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:  # keep the console clean
        return


class QuietThreadingServer(ThreadingHTTPServer):
    """Threading HTTP server with a registry handle the handlers read."""

    daemon_threads = True
    allow_reuse_address = True
    registry: DeviceBridge


def start_bridge(
    bridge: DeviceBridge,
    *,
    host: str = "0.0.0.0",
    port: int = 8711,
    on_ready: Callable[[str], None] | None = None,
) -> QuietThreadingServer | None:
    """Start the LAN bridge on a background thread and never block the caller.

    A second session launched while one already runs gets a busy port; that
    must never take the whole session down - the phone simply belongs to the
    first Kayla. Returns ``None`` and skips device controls in that case.
    """
    try:
        server = QuietThreadingServer((host, port), _BridgeHandler)
    except OSError as error:
        print(
            f"Phone bridge port {port} is busy ({error.strerror}); "
            "another Kayla session may already own it - device controls "
            "stay off in this one."
        )
        return None
    server.registry = bridge
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="kayla-device-bridge")
    thread.start()
    if on_ready is not None:
        on_ready(f"http://{host}:{port}")
    return server
