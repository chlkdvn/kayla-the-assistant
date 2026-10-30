# The floating orb (Kayla's pop-out body)

The orb is the little always-on-top window that floats over your desktop and
shows which state Kayla is in. It replaces the old 2D face window in realtime
mode (`face/` stays in the codebase and still works when you disable the orb).

## What you see

A software-3D scene, no GPU or model needed: a fibonacci-sphere particle
shell in two orbiting rings around a glowing core, with a breathing shimmer.
One short band under it can carry a message ("standing by") or the
**choice chips** — tap-able answers to a question. Colors mean energy:

| Energy   | Meaning                                |
| -------- | -------------------------------------- |
| idle     | resting, awake                         |
| listening| hearing you / awake after wake word    |
| thinking | working on a reply                     |
| speaking | talking (with a speaking pulse)        |
| working  | firm task energy (work mode, "angry")  |
| sleeping | silent: shutup/standby, wake-gate sleep|

## How to get one

- Type `kayla` in any terminal (or launch the *Kayla* app from GNOME search).
  That is the **pop-out front door**: it detaches the voice session from the
  terminal, closes the terminal, and the orb just hovers. If an orb is already
  running, the command focuses it instead of starting a twin.
- `uv run kayla-realtime` also opens one (it is part of realtime mode).
- `uv run kayla-orb` runs the orb window alone, for fiddling.

## Interaction

- **Drag**: grab anywhere on the orb body (not a chip). On X11 the first
  click hands the drag to the window manager via `_NET_WM_MOVERESIZE`
  (`orb/x11drag.py`), so GNOME moves her natively and she glides instead of
  buzzing — self-moving a borderless window per event is exactly what buzzed.
  Where X11 is unavailable she falls back to recomputing the whole offset
  from a fixed grab anchor on every motion event (never accumulated deltas).
- **Snap**: one quiet frame after the drag ends, a drop near an edge or
  corner settles her into a named slot; the position lives in
  `~/.config/kayla/orb_position.json` across restarts.
- **Chips**: at session start she asks how to begin - *Work mode / Focus mode /
  Best performance / All good* - as tap-able chips; clicking applies it
  immediately (mode change, notifications off, power profile) without a model
  turn. Escape dismisses a question, answering nothing.
- **Escape** (no question open) closes the orb.
- **Voice works too**: "move to the left side" moves her body via the
  `move_orb` tool.

### Small screens

She takes care of herself on a small laptop: her size at startup is fitted
into the work area (a fraction of width/height with sensible floors), she is
clamped fully on-screen, and a screen-scaled margin grows with the display.
The work area comes from `wmctrl -d` — never `wmctrl -lG`, whose coordinates
print doubled on some machines (this notebook included), while the ctypes
probe in `orb/x11drag.py` reads the true geometry when a process needs it.
Narrow windows shrink the chip question: the title steps down a font size and
chips wrap into up to three bottom-anchored rows.

## Protocol (port 8766)

`kayla/orb/client.py` is Kayla's voice; anything can be a client. One JSON
line per message, one plain reply line back:

- `ping` → `pong` (single-instance check)
- `state <energy|mood word>` → `ok` (moods map onto energies)
- `speak 1|0` → `ok` (speaking pulse)
- `look <x> <y>` → `ok` (gaze point)
- `msg <text>` → `ok` (status band)
- `ask {"title": ..., "options": [...]}` → `ok` then, later, `answer <n|-1>`
  (the two-step chip question; -1 = dismissed or 300 s timeout)
- `move <slot|x y>` → `ok` (named slot or absolute pixels)
- `focus` → `ok` (raise/scroll-on-top; the "already running" activation)
- `quit` → `ok` (clean shutdown; position saved first)

Slots: `top_left top top_right left center right bottom_left bottom bottom_right`.
`parse_position` forgives spoken forms ("top-left", "left top", "middle",
"bottom right corner").

## Lifecycle notes

- The orb starts **detached** so closing a terminal can never take it down.
- SIGTERM/SIGINT shut it down cleanly (SDL otherwise swallows them); the save
  position runs before the window closes.
- The command protocol is ASCII lines on `127.0.0.1` only, no auth by design;
  it is a local window controller (`KAYLA_ORB_HOST` to change).
- Realtime connects via `open_orb_window(settings)`, growing an `OrbClient`
  usable by the session for mood, lip-sync, message band, `ask`, and `move_orb`.

## Settings

```
KAYLA_ORB_ENABLED=true   KAYLA_ORB_AUTOSTART=true  KAYLA_ORB_HOST=127.0.0.1
KAYLA_ORB_PORT=8766      KAYLA_ORB_WIDTH=420       KAYLA_ORB_HEIGHT=260
KAYLA_ORB_OPACITY=0.96   # 0.2 .. 1.0
```

## Modules

- `orb/state.py` — OrbState, energy map, slots math, position persistence.
- `orb/render.py` — the 3D renderer and chip/messaging layout.
- `orb/app.py` — the window process: events, drag, snap, protocol server.
- `orb/client.py` — `OrbClient`, what the brain talks to the window with.
- `orb/window.py` — `open_orb_window`, shared by realtime and the wake gate.
- `orb/x11drag.py` — ctypes `libX11`: the WM drag handoff, `_NET_WM_PID`
  window matching, and the true-geometry probe (no new dependencies).
