"""Hand the orb's drag to the X11 window manager (GNOME/X11 smoothness).

Our borderless window cannot be dragged smoothly by moving it per event: the
motion coordinates SDL reports are relative to a window that is itself moving,
so the movement feeds back through the compositor and the orb buzzes instead
of gliding. Every borderless launcher on GNOME avoids this the same way - on
the first click it sends the manager a ``_NET_WM_MOVERESIZE`` request, and the
manager drags the window natively with the pointer until the button release.

Everything here goes through ``ctypes`` against the system ``libX11``: no new
dependencies, and every helper fails soft (returns False/None) so the orb
falls back to its own pointer math when X11 is unavailable (Wayland, tests).
"""

from __future__ import annotations

import ctypes
import threading

# X11 kit needed: type 33 = ClientMessage event, EWMH move direction 8 =
# _NET_WM_MOVERESIZE_MOVE (the manager tracks the pointer like a titlebar).
_CLIENT_MESSAGE = 33
_MOVERESIZE_MOVE = 8
_DRAG_BUTTON = 1
_SUBSTRUCTURE_REDIRECT = 1 << 20
_SUBSTRUCTURE_NOTIFY = 1 << 19
_XA_CARDINAL = 6

_LIB = None
_LOCK = threading.Lock()


class _ClientMessageEvent(ctypes.Structure):
    """``XClientMessageEvent`` with the C ABI on Linux/64-bit X11."""

    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("message_type", ctypes.c_ulong),
        ("format", ctypes.c_int),
        ("data", ctypes.c_long * 5),
    ]


def build_moveresize_event(x11_window: int, root_x: int, root_y: int) -> _ClientMessageEvent:
    """The ``_NET_WM_MOVERESIZE`` ClientMessage the root window expects."""
    message = _ClientMessageEvent()
    message.type = _CLIENT_MESSAGE
    message.window = x11_window
    message.message_type = 0  # the caller interns the real atom; kept for tests
    message.format = 32
    for slot, value in enumerate((x11_window, root_x, root_y, _MOVERESIZE_MOVE, _DRAG_BUTTON)):
        message.data[slot] = value
    return message


def drag_words(message: _ClientMessageEvent) -> tuple[int, ...]:
    """The five wire words of the message (tests read them back)."""
    return tuple(message.data)


def _load_xlib() -> ctypes.CDLL | None:
    """The system libX11, loaded once with the prototypes we use."""
    global _LIB
    with _LOCK:
        if _LIB is not None:
            return _LIB
        for name in ("libX11.so.6", "libX11.so"):
            try:
                lib = ctypes.CDLL(name)
            except OSError:
                continue
            lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            lib.XCloseDisplay.restype = ctypes.c_int
            lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            lib.XDefaultRootWindow.restype = ctypes.c_ulong
            lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            lib.XInternAtom.restype = ctypes.c_ulong
            lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            lib.XQueryTree.restype = ctypes.c_int
            lib.XQueryTree.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                ctypes.POINTER(ctypes.c_uint),
            ]
            lib.XGetWindowProperty.restype = ctypes.c_int
            lib.XGetWindowProperty.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_long,
                ctypes.c_long,
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
            ]
            lib.XQueryPointer.restype = ctypes.c_int
            lib.XQueryPointer.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_ulong),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_int),
                ctypes.POINTER(ctypes.c_uint),
            ]
            lib.XSendEvent.restype = ctypes.c_int
            lib.XSendEvent.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_int,
                ctypes.c_long,
                ctypes.c_void_p,
            ]
            lib.XFlush.restype = ctypes.c_int
            lib.XFlush.argtypes = [ctypes.c_void_p]
            _LIB = lib
            return lib
    return None


def _window_for_pid(lib: ctypes.CDLL, dpy: int, root: int, pid: int) -> int:
    """The X11 window id carrying our ``_NET_WM_PID`` among the root's children."""
    root_return = ctypes.c_ulong()
    parent = ctypes.c_ulong()
    count = ctypes.c_uint()
    children = ctypes.POINTER(ctypes.c_ulong)()
    if not lib.XQueryTree(
        dpy,
        root,
        ctypes.byref(root_return),
        ctypes.byref(parent),
        ctypes.byref(children),
        ctypes.byref(count),  # noqa: E501
    ):
        return 0
    try:
        atom = lib.XInternAtom(dpy, b"_NET_WM_PID", False)
        if not atom:
            return 0
        for index in range(count.value):
            window = children[index]
            if _cardinal_property(lib, dpy, window, atom) == pid:
                return window
    finally:
        if children:
            lib.XFree(children)  # type: ignore[attr-defined]
    return 0


def _cardinal_property(lib: ctypes.CDLL, dpy: int, window: int, atom: int) -> int:
    """First 32-bit word of a window property; -1 when absent."""
    actual_type = ctypes.c_ulong()
    actual_format = ctypes.c_int()
    items = ctypes.c_ulong()
    after = ctypes.c_ulong()
    data = ctypes.POINTER(ctypes.c_ubyte)()
    ok = lib.XGetWindowProperty(
        dpy,
        window,
        atom,
        0,
        4,
        False,
        _XA_CARDINAL,
        ctypes.byref(actual_type),
        ctypes.byref(actual_format),
        ctypes.byref(items),
        ctypes.byref(after),
        ctypes.byref(data),
    )
    # X returns Status codes where Success == 0: zero is good here.
    if ok != 0 or not data or actual_format.value != 32 or items.value < 1:
        return -1
    try:
        # Format-32 properties are stored as C longs on this arch; copy the
        # first long out with an explicit bound check (partial reads crash).
        value = ctypes.c_long()
        bytes_to_copy = min(ctypes.sizeof(ctypes.c_long), items.value * 8)
        ctypes.memmove(ctypes.byref(value), data, bytes_to_copy)
        return value.value
    finally:
        lib.XFree(data)  # type: ignore[attr-defined]
    words = ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))
    try:
        return words[0]
    finally:
        lib.XFree(data)  # type: ignore[attr-defined]


def _pointer_position(lib: ctypes.CDLL, dpy: int, root: int) -> tuple[int, int] | None:
    """Pointer position in root coordinates, or None when off any screen."""
    _root = ctypes.c_ulong()
    child = ctypes.c_ulong()
    root_x = ctypes.c_int()
    root_y = ctypes.c_int()
    _win_x = ctypes.c_int()
    _win_y = ctypes.c_int()
    mask = ctypes.c_uint()
    inside = lib.XQueryPointer(
        dpy,
        root,
        ctypes.byref(_root),
        ctypes.byref(child),
        ctypes.byref(root_x),
        ctypes.byref(root_y),
        ctypes.byref(_win_x),
        ctypes.byref(_win_y),
        ctypes.byref(mask),
    )
    if not inside:
        return None
    return root_x.value, root_y.value


def probe_geometry(pid: int) -> tuple[int, int, int, int] | None:
    """Real ``(x, y, width, height)`` of this pid's window in root coordinates.

    SDL keeps its own idea of the window position which may live in a
    different coordinate space than the desktop (scaled laptops, DPI
    transforms); the window manager's numbers are the ones slots, snapping
    and the position file must speak.
    """
    try:
        lib = _load_xlib()
        if lib is None:
            return None
        dpy = lib.XOpenDisplay(None)
        if not dpy:
            return None
        try:
            root = lib.XDefaultRootWindow(dpy)
            window = _window_for_pid(lib, dpy, root, pid)
            if not window:
                return None
            return _absolute_geometry(lib, dpy, root, window)
        finally:
            lib.XCloseDisplay(dpy)
    except Exception:  # noqa: BLE001 - measurement is optional sugar
        return None


def _absolute_geometry(
    lib: ctypes.CDLL, dpy: int, root: int, window: int
) -> tuple[int, int, int, int] | None:
    """Honest desktop coordinates: ``XTranslateCoordinates`` + ``XGetGeometry``."""
    abs_x = ctypes.c_int()
    abs_y = ctypes.c_int()
    child = ctypes.c_ulong()
    if not lib.XTranslateCoordinates(
        dpy, window, root, 0, 0, ctypes.byref(abs_x), ctypes.byref(abs_y), ctypes.byref(child)
    ):
        return None

    try:
        lib.XGetGeometry.restype = ctypes.c_int
        lib.XGetGeometry.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
        ]
    except AttributeError:  # pragma: no cover - prototypes set here already
        return None

    root_return = ctypes.c_ulong()
    _x = ctypes.c_int()
    _y = ctypes.c_int()
    width = ctypes.c_uint()
    height = ctypes.c_uint()
    border = ctypes.c_uint()
    _depth = ctypes.c_uint()
    if not lib.XGetGeometry(
        dpy,
        window,
        ctypes.byref(root_return),
        ctypes.byref(_x),
        ctypes.byref(_y),
        ctypes.byref(width),
        ctypes.byref(height),
        ctypes.byref(border),
        ctypes.byref(_depth),
    ):
        return None
    return abs_x.value, abs_y.value, width.value, height.value


def request_window_drag(pid: int) -> bool:
    """Tell the manager to drag this pid's window until the button releases.

    Returns True when the message was accepted and the orb should no longer
    move itself; False means the caller keeps its own fallback drag math.
    """
    try:
        lib = _load_xlib()
        if lib is None:
            return False
        dpy = lib.XOpenDisplay(None)
        if not dpy:
            return False
        try:
            root = lib.XDefaultRootWindow(dpy)
            if not root:
                return False
            window = _window_for_pid(lib, dpy, root, pid)
            if not window:
                return False
            pointer = _pointer_position(lib, dpy, root)
            if pointer is None:
                return False
            atom = lib.XInternAtom(dpy, b"_NET_WM_MOVERESIZE", False)
            if not atom:
                return False
            message = build_moveresize_event(window, pointer[0], pointer[1])
            message.message_type = atom
            sent = lib.XSendEvent(
                dpy,
                root,
                False,
                _SUBSTRUCTURE_REDIRECT | _SUBSTRUCTURE_NOTIFY,
                ctypes.byref(message),
            )
            lib.XFlush(dpy)
            return bool(sent)
        finally:
            lib.XCloseDisplay(dpy)
    except Exception:  # noqa: BLE001 - a lost drag never crashes the orb
        return False
