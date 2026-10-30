"""Offline tests for the orb's state logic, protocol, renderer, and client."""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import pygame
import pytest

from kayla.orb.app import (
    OrbRuntime,
    _move_window_to_slot,
    _snap_margin,
    _snap_or_save,
    handle_line,
    manual_drag_target,
)
from kayla.orb.client import OrbClient
from kayla.orb.render import ENERGY_STYLE, OrbRenderer, fibonacci_sphere, rotate_point
from kayla.orb.state import (
    OrbState,
    Question,
    clamp_into_area,
    energy_for_word,
    fit_window_size,
    load_position,
    parse_position,
    save_position,
    slot_for_window,
    slot_point,
    snap_position,
)

# --------------------------------------------------------------- state logic


def test_energy_for_word_maps_moods_and_energies():
    assert energy_for_word("sleeping") == "sleeping"
    assert energy_for_word("happy") == "working"
    assert energy_for_word("THINKING") == "thinking"
    assert energy_for_word("gibberish") == "idle"


def test_parse_position_tolerates_spoken_forms():
    assert parse_position("left") == "left"
    assert parse_position("Top Left") == "top_left"
    assert parse_position("top-left") == "top_left"
    assert parse_position("left top") == "top_left"
    assert parse_position("middle") == "center"
    assert parse_position("bottom right corner") == "bottom_right"
    assert parse_position("somewhere") is None


def test_snap_position_places_slots():
    assert snap_position("left", 100, 80, 1000, 800) == (28, 360)
    assert snap_position("top_right", 100, 80, 1000, 800) == (872, 28)
    assert snap_position("bottom_right", 100, 80, 1000, 800) == (872, 692)
    assert snap_position("center", 100, 80, 1000, 800) == (450, 360)
    assert snap_position("top", 100, 80, 1000, 800) == (450, 28)


def test_slot_for_window_from_dragged_position():
    assert slot_for_window(5, 400, 100, 80, 1000, 800) == "left"
    assert slot_for_window(900, 5, 100, 80, 1000, 800) == "top_right"
    assert slot_for_window(500, 700, 100, 80, 1000, 800) == "bottom"
    assert slot_for_window(400, 200, 100, 80, 1000, 800) is None


# --------------------------------------------------- small-screen work area


def test_slot_point_offsets_into_the_work_area():
    # A 30px top bar: "left" hugs the visible edge with room above the bar.
    x, y = slot_point("left", 355, 220, (0, 30, 1366, 738), margin=18)
    assert (x, y) == (18, 30 + (738 - 220) // 2)
    x, y = slot_point("bottom_right", 355, 220, (0, 30, 1366, 738), margin=18)
    assert (x, y) == (1366 - 355 - 18, 30 + (738 - 220 - 18))


def test_fit_window_size_shrinks_on_the_laptop_area():
    # 420x260 is a third of a 1366 work area; ~26% keeps her kind on a laptop.
    assert fit_window_size(420, 260, (0, 30, 1366, 738)) == (355, 220)
    # A big screen keeps her full size; no area falls back to unshrunk.
    assert fit_window_size(420, 260, (0, 0, 2560, 1440)) == (420, 260)
    assert fit_window_size(420, 260, None) == (420, 260)
    # Tiny areas cannot shrink her below readable floors.
    assert fit_window_size(420, 260, (0, 0, 500, 400)) == (240, 150)


def test_clamp_into_area_keeps_remembered_positions_visible():
    area = (0, 30, 1366, 738)
    assert clamp_into_area(-50, 10, 355, 220, area) == (0, 30)
    assert clamp_into_area(2000, 3000, 355, 220, area) == (1011, 548)
    assert clamp_into_area(100, 200, 355, 220, area) == (100, 200)
    assert clamp_into_area(100, 200, 355, 220, None) == (100, 200)


def test_snap_margin_scales_with_the_work_area():
    assert _snap_margin((0, 30, 1366, 738)) == 18
    assert _snap_margin(None) == 28
    assert _snap_margin((0, 0, 800, 300)) >= 6


def test_read_work_area_parses_or_gives_up(monkeypatch):
    import types

    import kayla.orb.app as orb_app

    real_output = "0  * DG: 1366x768  VP: 0,0  WA: 0,30 1366x738  Workspace 1\n"
    good = types.SimpleNamespace(returncode=0, stdout=real_output, stderr="")
    monkeypatch.setattr(orb_app.subprocess, "run", lambda argv, **kw: good)
    assert orb_app._read_work_area() == (0, 30, 1366, 738)

    bad = types.SimpleNamespace(returncode=1, stdout="", stderr="broken")
    monkeypatch.setattr(orb_app.subprocess, "run", lambda argv, **kw: bad)
    assert orb_app._read_work_area() is None

    def explode(argv, **kw):
        raise FileNotFoundError("wmctrl not installed")

    monkeypatch.setattr(orb_app.subprocess, "run", explode)
    assert orb_app._read_work_area() is None


class _FakeWindow:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.position = (x, y)
        self.size = (width, height)


def test_manual_drag_target_recomputes_from_the_fixed_anchor():
    # The window sat at (100, 200) when the pointer grabbed her at (50, 30)
    # inside the window; pointer now at (80, 40) means she must move by the
    # pointer travel only, recomputed absolutely (no accumulation, no shake).
    assert manual_drag_target((100, 200), (50, 30), (80, 40)) == (130, 210)


def test_move_window_to_slot_uses_the_work_area(tmp_path):
    window = _FakeWindow(0, 0, 355, 220)
    _move_window_to_slot(window, "bottom_right", (0, 30, 1366, 738), 18, tmp_path / "pos.json")
    assert window.position == (1366 - 355 - 18, 30 + (738 - 220 - 18))
    assert load_position(tmp_path / "pos.json") == window.position


def test_snap_or_save_snaps_to_work_area_edges(tmp_path):
    window = _FakeWindow(0, 40, 355, 220)
    _snap_or_save(window, (0, 30, 1366, 738), 18, tmp_path / "pos.json")
    # Hugging the top-left of the visible area snaps her into the top_left slot.
    assert window.position == (18, 48)
    assert load_position(tmp_path / "pos.json") == (18, 48)


def test_snap_or_save_keeps_free_positions(tmp_path):
    window = _FakeWindow(400, 200, 355, 220)
    _snap_or_save(window, (0, 30, 1366, 738), 18, tmp_path / "pos.json")
    assert window.position == (400, 200)
    assert load_position(tmp_path / "pos.json") == (400, 200)


def test_position_persistence_roundtrip(tmp_path: Path):
    path = tmp_path / "orb_position.json"
    assert load_position(path) is None
    save_position(path, 120, 88)
    assert load_position(path) == (120, 88)
    path.write_text("not json")
    assert load_position(path) is None


# ----------------------------------------------------------------- protocol


def test_handle_line_basic_commands():
    runtime = OrbRuntime()
    assert handle_line("ping", runtime) == "pong"
    assert handle_line("state thinking", runtime) == "ok"
    assert runtime.snapshot()[0] == "thinking"
    assert handle_line("speak 1", runtime) == "ok"
    assert runtime.snapshot()[1] is True
    assert handle_line("look 0.5 -0.25", runtime) == "ok"
    assert runtime.snapshot()[2] == (0.5, -0.25)
    assert handle_line("msg charging, be right back", runtime) == "ok"
    assert runtime.snapshot()[3] == "charging, be right back"


def test_handle_line_mood_words_map_to_energies():
    runtime = OrbRuntime()
    assert handle_line("state angry", runtime) == "ok"
    assert runtime.snapshot()[0] == "working"


def test_handle_line_move_queue_and_errors():
    runtime = OrbRuntime()
    assert handle_line("move left", runtime) == "ok"
    assert runtime.pending_labels == ["left"]
    assert handle_line("pos 11 22", runtime) == "ok"
    assert runtime.pending_moves == [(11, 22)]
    assert handle_line("pos 11", runtime) == "err"
    assert handle_line("move nowhere", runtime) == "err"
    assert handle_line("nonsense", runtime) == "?"


def test_ask_flow_and_dismissal():
    runtime = OrbRuntime()
    payload = json.dumps({"title": "How should we start?", "options": ["Work", "Chill"]})
    assert handle_line(f"ask {payload}", runtime) == "ok"
    assert runtime.has_question()
    runtime.answer_question(1)
    assert runtime.pop_answer() == 1
    assert not runtime.has_question()

    handle_line(f"ask {payload}", runtime)
    runtime.dismiss_question()
    assert runtime.pop_answer() is None


# ----------------------------------------------------------------- renderer


@pytest.fixture(scope="module")
def pygame_ready():
    pygame.init()
    yield
    pygame.quit()


def test_fibonacci_and_rotation_math():
    points = fibonacci_sphere(10)
    assert len(points) == 10
    for x, y, z in points:
        assert abs((x * x + y * y + z * z) - 1.0) < 1e-9
    assert rotate_point((0.0, 0.0, 1.0), 0.0, 0.0) == (0.0, 0.0, 1.0)
    x, y, z = rotate_point((0.0, 0.0, 1.0), yaw=0.5, pitch=0.0)
    assert x == pytest.approx(1.0, abs=1e-6) or x < 1.0  # yaw moves z toward x
    assert z == pytest.approx(0.8775825619, abs=1e-6)


def test_all_energies_have_styles():
    for energy in ("idle", "listening", "thinking", "speaking", "working", "sleeping"):
        assert energy in ENERGY_STYLE


def test_renderer_draws_every_state_without_crash(pygame_ready):
    canvas = pygame.Surface((840, 520))
    renderer = OrbRenderer(840, 520)
    for energy in ("idle", "speaking", "sleeping"):
        for question in (None, None):
            state = OrbState(energy=energy, speaking=energy == "speaking")
            if question is not None:
                from kayla.orb.state import Question

                state.question = Question(title="Ready?", options=["Work", "Chill"])
            chips = renderer.draw(canvas, state, t=1.0)
            if state.question is not None:
                assert len(chips) == 2
            else:
                assert chips == []


def _question_state(options: list[str]) -> OrbState:
    question = Question(title="How should we start?", options=options)
    return OrbState(energy="idle", speaking=False, question=question)


def test_question_chips_wrap_and_stay_on_the_panel(pygame_ready):
    four = ["Work with the code", "Focus on the writing", "School research", "Chill and rest"]
    for canvas_w in (840, 710):  # roomy window and the laptop-fitted ~355px window
        renderer = OrbRenderer(canvas_w, 520)
        title_y, chips, chip_size = renderer.question_layout(_question_state(four))
        assert len(chips) == 4
        assert title_y is not None
        assert title_y < chips[0].top  # the title sits above the chip block
        assert chips[-1].bottom <= 520  # anchored at the bottom, never off-panel
        assert all(rect.right <= canvas_w for rect in chips)  # no spilling to the right


def test_question_chips_shrink_the_font_before_overflowing(pygame_ready):
    crowded = ["Continue the migration work", "Focus writing session", "School plan", "Chill"]
    renderer = OrbRenderer(710, 520)
    _title_y, chips, chip_size = renderer.question_layout(_question_state(crowded))
    assert len(chips) == 4
    assert all(rect.right <= 710 for rect in chips)
    assert chip_size == 30  # these four still fit side by side after wrapping


def test_question_layout_without_a_question_is_empty(pygame_ready):
    renderer = OrbRenderer(840, 520)
    title_y, chips, _size = renderer.question_layout(OrbState())
    assert title_y is None
    assert chips == []


# ------------------------------------------------------------------- client


def test_client_roundtrip_against_live_protocol():
    runtime = OrbRuntime()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    threading.Thread(target=_serve, args=(server, runtime), daemon=True).start()

    client = OrbClient("127.0.0.1", port)
    client.set_mood("thinking")
    _wait_for(lambda: runtime.snapshot()[0] == "thinking")
    client.message("hello orb")
    _wait_for(lambda: runtime.snapshot()[3] == "hello orb")

    assert client.command("ping") == "pong"
    assert client.ping() is True
    client.close()
    server.close()


def test_client_ask_delivers_chip_choice():
    runtime = OrbRuntime()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    threading.Thread(target=_serve, args=(server, runtime), daemon=True).start()
    client = OrbClient("127.0.0.1", port)

    result: list[int | None] = []

    def asker() -> None:
        result.append(client.ask("Ready?", ["Work", "Chill"], timeout=8))

    worker = threading.Thread(target=asker, daemon=True)
    worker.start()
    _wait_for(runtime.has_question)
    runtime.answer_question(1)
    worker.join(5)
    assert result == [1]

    # A dismissed question answers None cleanly.
    dropped: list[int | None] = []

    def second_asker() -> None:
        dropped.append(client.ask("Again?", ["No"], timeout=0.4))

    worker = threading.Thread(target=second_asker, daemon=True)
    worker.start()
    worker.join(5)
    assert dropped == [None]
    runtime.dismiss_question()  # free the server-side wait
    client.close()
    server.close()


def _serve(server: socket.socket, runtime: OrbRuntime) -> None:
    server.listen(8)
    while True:
        try:
            conn, _addr = server.accept()
        except OSError:
            return
        threading.Thread(target=_client_protocol, args=(conn, runtime), daemon=True).start()


def _client_protocol(conn: socket.socket, runtime: OrbRuntime) -> None:
    from kayla.orb.app import handle_connection

    handle_connection(conn, runtime)


def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached in time")
