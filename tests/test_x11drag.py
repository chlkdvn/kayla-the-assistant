"""Offline tests for the window-manager drag handoff (pure message assembly)."""

from __future__ import annotations

from kayla.orb import x11drag


def test_moveresize_message_carries_window_and_move_direction():
    message = x11drag.build_moveresize_event(0x2600002, 500, 400)

    assert message.type == 33  # ClientMessage event on the wire
    assert message.window == 0x2600002
    assert message.format == 32  # long words, as EWMH demands
    assert x11drag.drag_words(message) == (
        0x2600002,  # the window that should be dragged
        500,  # grabbing pointer, root x
        400,  # grabbing pointer, root y
        x11drag._MOVERESIZE_MOVE,  # direction: manager tracks the pointer
        x11drag._DRAG_BUTTON,  # which button started it
    )


def test_direction_8_is_the_pointer_move_gesture():
    assert x11drag._MOVERESIZE_MOVE == 8


def test_request_drag_gives_up_gracefully_without_x11(monkeypatch):
    monkeypatch.setattr(x11drag, "_load_xlib", lambda: None)

    assert x11drag.request_window_drag(999) is False
    assert x11drag.probe_geometry(999) is None
