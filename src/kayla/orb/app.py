"""Run Kayla's floating 3D orb window and let her brain drive it over a socket.

    uv run kayla-orb --demo    # cycle energies to see the orb alive
    uv run kayla-orb           # wait for the brain on 127.0.0.1:8766

The window is borderless and always on top, can be dragged anywhere (snapping
to screen edges), and remembers its position between runs. The socket speaks
one command per line:

    ping            -> pong
    state <word>    -> ok      (energy or classic face mood)
    speak <0|1>     -> ok      (equalizer on/off)
    look <x> <y>    -> ok      (-1..1, tilts the sphere)
    msg <text>      -> ok      (status line under the orb)
    move <label>    -> ok      (left/right/top/... recomputed from the screen)
    pos <x> <y>     -> ok      (absolute move)
    focus           -> ok      (raise the window)
    quit            -> ok      (close the orb)
    ask {json}      -> ok, then later a second reply:  answer <n> | answer -1

``ask`` carries ``{"title": ..., "options": [...]}`` and is how the orb shows
its startup chips ("Work mode", "Focus mode", ...) to the brain.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pygame

from kayla.orb import x11drag
from kayla.orb.render import OrbRenderer
from kayla.orb.state import (
    DEFAULT_POSITION_FILE,
    OrbState,
    Question,
    clamp_into_area,
    fit_window_size,
    load_position,
    parse_position,
    save_position,
    slot_for_window,
    slot_point,
)
from kayla.system.monitor import parse_work_area

QUESTION_TIMEOUT = 300  # seconds a chip question stays open before answer -1


class OrbRuntime:
    """Thread-safe bridge between socket threads and the render loop."""

    def __init__(self) -> None:
        self.state = OrbState()
        self._lock = threading.Lock()
        self.answer_event = threading.Event()
        self.answer_value: int | None = None
        self.pending_moves: list[tuple[int, int]] = []
        self.pending_labels: list[str] = []
        self.pending_focus = False
        self.stop_requested = False

    # -- render-loop reads (plain fields, guarded swaps) ------------------

    def snapshot(self) -> tuple[str, bool, tuple[float, float], str, Question | None]:
        with self._lock:
            state = self.state
            return (
                state.energy,
                state.speaking,
                state.look,
                state.message,
                state.question,
            )

    # -- socket-thread writes ---------------------------------------------

    def set_energy(self, word: str) -> None:
        with self._lock:
            self.state.apply_energy(word)

    def set_speaking(self, speaking: bool) -> None:
        with self._lock:
            self.state.speaking = speaking

    def set_look(self, x: float, y: float) -> None:
        with self._lock:
            self.state.look = (max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y)))

    def set_message(self, text: str) -> None:
        with self._lock:
            self.state.message = text[:120]

    def open_question(self, title: str, options: list[str]) -> None:
        with self._lock:
            self.state.question = Question(title=title[:80], options=options[:4])
        self.answer_value = None
        self.answer_event.clear()

    def answer_question(self, index: int) -> None:
        self.answer_value = index
        self.answer_event.set()

    def has_question(self) -> bool:
        with self._lock:
            return self.state.question is not None

    def dismiss_question(self) -> None:
        with self._lock:
            self.state.question = None
        self.answer_value = None
        self.answer_event.set()  # the waiting reply becomes answer -1

    def pop_answer(self) -> int | None:
        with self._lock:
            self.state.question = None
        value = self.answer_value
        self.answer_value = None
        return value

    # -- window actions queued for the main loop ---------------------------

    def request_move_label(self, label: str) -> None:
        self.pending_labels.append(label)

    def request_move_xy(self, x: int, y: int) -> None:
        self.pending_moves.append((int(x), int(y)))

    def request_focus(self) -> None:
        self.pending_focus = True

    def request_stop(self) -> None:
        self.stop_requested = True


def handle_line(line: str, runtime: OrbRuntime) -> str:
    """Parse one protocol line, mutate the runtime, return the wire reply."""
    command, _, rest = line.partition(" ")
    command = command.casefold()
    rest = rest.strip()
    if command == "ping":
        return "pong"
    if command in {"state", "energy", "mode"} and rest:
        runtime.set_energy(rest.casefold())
        return "ok"
    if command == "speak" and rest:
        runtime.set_speaking(rest.casefold() not in {"0", "off", "false", "no"})
        return "ok"
    if command == "look" and rest:
        pieces = rest.split()
        if len(pieces) != 2:
            return "err"
        try:
            runtime.set_look(float(pieces[0]), float(pieces[1]))
        except ValueError:
            return "err"
        return "ok"
    if command == "msg" and rest:
        runtime.set_message(rest)
        return "ok"
    if command == "ask" and rest:
        try:
            payload = json.loads(rest)
            title = str(payload.get("title", "")).strip()
            options = [
                str(option).strip() for option in payload.get("options", []) if str(option).strip()
            ]
        except (ValueError, AttributeError, TypeError):
            return "err"
        if not title or not options:
            return "err"
        runtime.open_question(title, options)
        return "ok"
    if command == "move" and rest:
        label = parse_position(rest)
        if label is None:
            return "err"
        runtime.request_move_label(label)
        return "ok"
    if command == "pos" and rest:
        pieces = rest.split()
        if len(pieces) != 2:
            return "err"
        try:
            runtime.request_move_xy(int(float(pieces[0])), int(float(pieces[1])))
        except ValueError:
            return "err"
        return "ok"
    if command == "focus":
        runtime.request_focus()
        return "ok"
    if command == "quit":
        runtime.request_stop()
        return "ok"
    return "?"


def handle_connection(conn: socket.socket, runtime: OrbRuntime) -> None:
    """Serve one client connection, including the duplex ``ask`` two-step."""
    with conn, conn.makefile("rwb") as stream:
        while True:
            try:
                raw = stream.readline()
            except OSError:
                break  # client vanished between messages; nothing to serve
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                reply = handle_line(line, runtime)
                stream.write((reply + "\n").encode())
                stream.flush()
                if line.split(maxsplit=1)[0].casefold() == "ask" and reply == "ok":
                    answered = runtime.answer_event.wait(timeout=QUESTION_TIMEOUT)
                    value = runtime.pop_answer() if answered else None
                    stream.write(f"answer {value if value is not None else -1}\n".encode())
                    stream.flush()
            except OSError:
                break


def serve(host: str, port: int, runtime: OrbRuntime) -> None:
    """Bind the command socket with small retries so restarts win the race."""
    last_error: OSError | None = None
    for _attempt in range(5):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((host, port))
            break
        except OSError as error:
            last_error = error
            server = None  # type: ignore[assignment]
            time.sleep(0.5)
    if server is None:
        raise RuntimeError(f"could not bind {host}:{port} ({last_error})")
    server.listen(8)
    while True:
        conn, _addr = server.accept()
        threading.Thread(target=handle_connection, args=(conn, runtime), daemon=True).start()


def _already_running(host: str, port: int) -> bool:
    """True when another orb owns the socket; bump it to the front."""
    try:
        with socket.create_connection((host, port), timeout=0.6) as conn:
            conn.sendall(b"focus\n")
            conn.settimeout(1.0)
            conn.recv(16)
        return True
    except OSError:
        return False


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kayla's floating 3D orb window.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--width", type=int, default=420)
    parser.add_argument("--height", type=int, default=260)
    parser.add_argument("--opacity", type=float, default=0.96)
    parser.add_argument("--position-path", default=str(DEFAULT_POSITION_FILE))
    parser.add_argument("--demo", action="store_true", help="cycle energies automatically")
    parser.add_argument("--second", action="store_true", help="open even if one is already up")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Own the window for the whole session; steals focus from a twin orb."""
    args = _parse_args(argv)
    if not args.second and _already_running(args.host, args.port):
        print("Kayla's orb is already up - focused it instead of opening another.")
        return

    pygame.init()
    work_area = _read_work_area()
    if work_area is None:
        # No wmctrl: fall back to the full desktop (no top-bar trimming).
        with contextlib.suppress(Exception):
            screen_w, screen_h = pygame.display.get_desktop_sizes()[0]
            work_area = (0, 0, screen_w, screen_h)
    # On a small screen she shrinks to a kind size instead of covering a
    # third of it; the remembered position is clamped back into view.
    width, height = fit_window_size(args.width, args.height, work_area)
    margin = _snap_margin(work_area)
    position_path = Path(args.position_path)
    position = load_position(position_path)
    if position is not None:
        position = clamp_into_area(position[0], position[1], width, height, work_area)
    window = pygame.Window(title="Kayla", size=(width, height), borderless=True, always_on_top=True)
    # Born borderless: SDL then treats window coordinates as plain desktop
    # pixels. A window created decorated and borderless *afterwards* makes
    # every later position set land ~46px high (SDL trims the frame it knew).
    if position is not None:
        with contextlib.suppress(AttributeError, pygame.error):
            window.position = position
    with contextlib.suppress(AttributeError, ValueError):
        window.opacity = max(0.2, min(1.0, args.opacity))

    runtime = OrbRuntime()
    try:
        threading.Thread(target=serve, args=(args.host, args.port, runtime), daemon=True).start()
    except RuntimeError as error:
        print(f"Orb socket unavailable ({error}); closing.")
        return
    print(f"Kayla's orb is up. Command socket: {args.host}:{args.port}")

    renderer = OrbRenderer(width * 2, height * 2)
    canvas = pygame.Surface((width * 2, height * 2))
    clock = pygame.time.Clock()
    # Drag state. The happy path hands the drag to the window manager
    # (_NET_WM_MOVERESIZE on X11), which is the only way a borderless window
    # glides on GNOME - SDL's own motion deltas are measured inside a window
    # that is itself moving, so self-moves fight the compositor and buzz.
    drag_wm_pending = False  # manager is dragging; release may never reach us
    drag_manual = False  # fallback: our own projected drag
    drag_grab: tuple[int, int] = (0, 0)  # grab point within the window
    drag_base: tuple[int, int] = (0, 0)  # window position at grab time
    drag_desired: tuple[int, int] | None = None  # queued manual move (1/frame)
    drag_end_pending = False  # snap one frame after any drag finishes
    hover_chip = -1
    chips: list = []  # chip rects from the previous frame, for hit-testing
    demo_index = 0
    demo_timer = 0.0
    DEMO_ENERGIES = ["listening", "thinking", "speaking", "working", "idle", "sleeping"]
    running = True
    # SDL swallows SIGTERM/SIGINT once a window is open, so handle them here:
    # the flag is checked every frame and the normal path saves the position.
    stop_flag: list[bool] = []

    def _request_quit(*_args: object) -> None:
        stop_flag.append(True)

    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(Exception):
            signal.signal(sig, _request_quit)
    while running and not stop_flag and not runtime.stop_requested:
        dt = clock.tick(60) / 1000.0
        t = time.monotonic()

        # Socket-queued window actions (never touch the window off-thread).
        while runtime.pending_labels:
            label = runtime.pending_labels.pop(0)
            _move_window_to_slot(window, label, work_area, margin, position_path)
        while runtime.pending_moves:
            x, y = runtime.pending_moves.pop(0)
            window.position = (x, y)
            save_position(position_path, x, y)
        if runtime.pending_focus:
            runtime.pending_focus = False
            with contextlib.suppress(AttributeError, pygame.error):
                window.focus()

        mouse_x, mouse_y = pygame.mouse.get_pos()
        hover_chip = _chip_at(chips, mouse_x * 2, mouse_y * 2)
        for event in pygame.event.get():
            if event.type == pygame.WINDOWCLOSE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if runtime.has_question():
                    runtime.dismiss_question()
                else:
                    running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = _chip_at(chips, event.pos[0] * 2, event.pos[1] * 2)
                if hit >= 0:
                    runtime.answer_question(hit)
                elif x11drag.request_window_drag(os.getpid()):
                    # The manager owns the drag from here to the release. We
                    # usually never see that release (it lands outside our
                    # surface and the manager holds the pointer), so the first
                    # unbuttoned motion below is what actually ends the drag.
                    drag_wm_pending = True
                else:
                    drag_manual = True
                    drag_grab = event.pos
                    drag_base = tuple(window.position)
            elif event.type == pygame.MOUSEMOTION:
                if drag_wm_pending and not event.buttons[0]:
                    drag_wm_pending = False  # manager drag is over; settle, then snap
                    drag_end_pending = True
                elif drag_manual:
                    if event.buttons[0]:
                        # Recompute the whole needed offset from the fixed grab
                        # point - absolute per event, never accumulated, so a
                        # lagging compositor cannot feed back and shake her.
                        drag_desired = manual_drag_target(drag_base, drag_grab, event.pos)
                    else:
                        drag_manual = False
                        drag_end_pending = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                drag_wm_pending = False
                if drag_manual or drag_desired is not None:
                    drag_manual = False
                    drag_end_pending = True

        # A queued manual move goes out once per frame, batched for the manager.
        if drag_manual and drag_desired is not None:
            window.position = drag_desired
            drag_desired = None
        # One quiet frame after a drag ends, then snap into an edge slot (or
        # just remember the free position) using the settled geometry.
        if drag_end_pending:
            drag_end_pending = False
            _snap_or_save(window, work_area, margin, position_path)

        if args.demo:
            demo_timer += dt
            if demo_timer >= 2.2:
                demo_timer = 0.0
                energy = DEMO_ENERGIES[demo_index % len(DEMO_ENERGIES)]
                runtime.set_energy(energy)
                runtime.set_speaking(energy == "speaking")
                demo_index += 1

        energy, speaking, look, message, question = runtime.snapshot()
        state = OrbState(
            energy=energy, speaking=speaking, look=look, message=message, question=question
        )
        chips = renderer.draw(canvas, state, t, hover_chip=hover_chip)
        screen = window.get_surface()
        scaled = pygame.transform.smoothscale(canvas, screen.get_size())
        screen.blit(scaled, (0, 0))
        window.flip()

    x, y = window.position
    save_position(position_path, x, y)
    pygame.quit()


def _chip_at(chips: list, x: int, y: int) -> int:
    """Index of the chip under the point (already in canvas scale), else -1."""
    for index, rect in enumerate(chips):
        if rect.collidepoint(x, y):
            return index
    return -1


def manual_drag_target(
    base: tuple[int, int], grab: tuple[int, int], pos: tuple[int, int]
) -> tuple[int, int]:
    """Fallback drag: the window target for the pointer's window-local ``pos``.

    ``base`` was the window position when the drag started and ``grab`` is
    where inside the window the pointer grabbed. The full offset is recomputed
    from that one fixed anchor at every motion event, so a lagging compositor
    can only make her pause, never shake.
    """
    return base[0] + pos[0] - grab[0], base[1] + pos[1] - grab[1]


def _read_work_area() -> tuple[int, int, int, int] | None:
    """Ask the window manager for the usable desktop area.

    Struts (the GNOME top bar, docks) mean the area is smaller than the
    screen: slots and the small-screen fit must use what the user can really
    see. None when wmctrl is missing or fails; callers then treat the whole
    screen as the area.
    """
    try:
        result = subprocess.run(
            ["wmctrl", "-d"], capture_output=True, text=True, timeout=4, check=False
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    return parse_work_area(result.stdout)


def _fallback_area() -> tuple[int, int, int, int]:
    """The whole first desktop, for when the window manager cannot tell us more."""
    try:
        screen_w, screen_h = pygame.display.get_desktop_sizes()[0]
    except Exception:  # noqa: BLE001 - headless tests must still pass
        screen_w, screen_h = 1280, 720
    return (0, 0, screen_w, screen_h)


def _snap_margin(area: tuple[int, int, int, int] | None) -> int:
    """Gap from the screen edge when she snaps into a slot.

    Scales with the work area (28 is ~4% of a 1920x1080 bar; 18 suits a
    1366x738 laptop) so snap positions don't crowd tiny screens.
    """
    if area is None:
        return 28
    return max(6, min(28, area[3] // 40))


def _move_window_to_slot(
    window: pygame.Window,
    label: str,
    area: tuple[int, int, int, int] | None,
    margin: int,
    position_path: Path,
) -> None:
    """Move the window into a named slot of the usable work area."""
    size = window.size
    resolved = area if area is not None else _fallback_area()
    x, y = slot_point(label, size[0], size[1], resolved, margin=margin)
    window.position = (x, y)
    save_position(position_path, x, y)


def _snap_or_save(
    window: pygame.Window,
    area: tuple[int, int, int, int] | None,
    margin: int,
    position_path: Path,
) -> None:
    """After a drag, snap into the nearest edge slot when one is under the cursor."""
    x, y = window.position
    width, height = window.size
    resolved = area if area is not None else _fallback_area()
    # slot_for_window works on area-relative coordinates, so a work area with
    # an origin (the top bar) smells its edges where they really are.
    slot = slot_for_window(
        x - resolved[0], y - resolved[1], width, height, resolved[2], resolved[3], margin=margin
    )
    if slot is not None:
        new_x, new_y = slot_point(slot, width, height, resolved, margin=margin)
        window.position = (new_x, new_y)
        save_position(position_path, new_x, new_y)
        return
    save_position(position_path, x, y)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
