"""Pure orb state: energies, spoken-position snapping, and position memory.

Kept free of pygame so tests cover the real logic without a display.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_POSITION_FILE = Path.home() / ".config" / "kayla" / "orb_position.json"

ENERGIES: tuple[str, ...] = (
    "idle",
    "listening",
    "thinking",
    "speaking",
    "working",
    "sleeping",
)

POSITIONS: tuple[str, ...] = (
    "top_left",
    "top",
    "top_right",
    "left",
    "center",
    "right",
    "bottom_left",
    "bottom",
    "bottom_right",
)

MOOD_WORDS: dict[str, str] = {
    # Classic face moods keep working on the orb: they map to energies.
    "normal": "idle",
    "calm": "idle",
    "alert": "listening",
    "sleeping": "sleeping",
    "tired": "sleeping",
    "thinking": "thinking",
    "typing": "thinking",
    "confused": "thinking",
    "listening": "listening",
    "hushed": "listening",
    "speaking": "speaking",
    "talkative": "speaking",
    "happy": "working",
    "excited": "working",
    "playful": "working",
    "love": "working",
    "surprised": "listening",
    "angry": "working",
    "sad": "sleeping",
    "work": "working",
    "idle": "idle",
}


def energy_for_word(word: str) -> str:
    """Map any spoken/typed word (energy or old face mood) onto an energy."""
    word = word.strip().casefold()
    if word in ENERGIES:
        return word
    if word in MOOD_WORDS:
        return MOOD_WORDS[word]
    return "idle"


def parse_position(word: str) -> str | None:
    """Turn a spoken spot ("top left", "middle", "right side") into a slot."""
    text = word.strip().casefold().replace("-", " ")
    tokens = [token for token in text.split() if token not in _JUNK_TOKENS]
    text = "_".join(tokens)
    text = {
        "middle": "center",
        "mid": "center",
        "tl": "top_left",
        "tr": "top_right",
        "bl": "bottom_left",
        "br": "bottom_right",
    }.get(text, text)
    for position in POSITIONS:
        if text == position:
            return position
    for position in POSITIONS:  # composite forms come second
        parts = position.split("_")
        if len(parts) == 2 and text == "_".join(reversed(parts)):
            # "left_top" maps to "top_left"; bare "left" is matched exactly above.
            return position
    return None


_JUNK_TOKENS = frozenset(
    {"corner", "screen", "side", "laptop", "to", "my", "the", "please", "corner,"}
)


def _slot_parts(label: str) -> tuple[str, str]:
    """Split a slot label into (horizontal, vertical) components."""
    if label in {"top", "bottom"}:
        return "center", label
    if label == "center":
        return "center", "center"
    if label in {"left", "right"}:
        return label, "center"
    first, _, last = label.partition("_")
    return last, first


def snap_position(
    label: str, window_w: int, window_h: int, screen_w: int, screen_h: int, *, margin: int = 28
) -> tuple[int, int]:
    """Absolute window position for a named screen slot (pure math)."""
    label = label if label in POSITIONS else "center"
    horizontal, vertical = _slot_parts(label)
    if horizontal == "left":
        x = margin
    elif horizontal == "right":
        x = screen_w - window_w - margin
    else:
        x = (screen_w - window_w) // 2
    if vertical == "top":
        y = margin
    elif vertical == "bottom":
        y = screen_h - window_h - margin
    else:
        y = (screen_h - window_h) // 2
    return max(0, x), max(0, y)


def slot_point(
    label: str,
    window_w: int,
    window_h: int,
    area: tuple[int, int, int, int],
    *,
    margin: int = 28,
) -> tuple[int, int]:
    """Top-left position for a slot inside a rectangular work area.

    ``area`` is ``(x, y, width, height)`` in global coordinates (a GNOME top
    bar makes it differ from the raw screen). The slot math assumes a 0-based
    screen, so the computed in-area point is offset by the area origin; this
    also keeps negative multi-monitor origins correct.
    """
    inner_x, inner_y = snap_position(
        label if label in POSITIONS else "center",
        window_w,
        window_h,
        max(area[2], 1),
        max(area[3], 1),
        margin=margin,
    )
    return area[0] + inner_x, area[1] + inner_y


def fit_window_size(
    width: int, height: int, area: tuple[int, int, int, int] | None
) -> tuple[int, int]:
    """Shrink the orb until it sits kindly on a small screen; never grow it.

    A 420x260 orb is a third of a 1366-pixel work area already, so on small
    screens she is scaled down proportionally (keeps her silhouette) toward
    roughly a quarter of the work area width. Floors keep her readable.
    """
    if area is None:
        return width, height
    _, _, area_w, area_h = area
    scale = min(1.0, (area_w * 0.26) / max(width, 1), (area_h * 0.45) / max(height, 1))
    if scale >= 1.0:
        return width, height
    return max(240, round(width * scale)), max(150, round(height * scale))


def clamp_into_area(
    x: int,
    y: int,
    window_w: int,
    window_h: int,
    area: tuple[int, int, int, int] | None,
) -> tuple[int, int]:
    """Keep a remembered window position on the visible work area."""
    if area is None:
        return x, y
    origin_x, origin_y, area_w, area_h = area
    max_x = origin_x + max(area_w - window_w, 0)
    max_y = origin_y + max(area_h - window_h, 0)
    return min(max(x, origin_x), max_x), min(max(y, origin_y), max_y)


def slot_for_window(
    x: int, y: int, window_w: int, window_h: int, screen_w: int, screen_h: int, *, margin: int = 28
) -> str | None:
    """When a dragged window sits in an edge band, name the slot it should snap into."""
    bands = {
        "left": x <= margin * 3,
        "right": x >= screen_w - window_w - margin * 3,
        "top": y <= margin * 3,
        "bottom": y >= screen_h - window_h - margin * 3,
    }
    matched = [name for name, hit in bands.items() if hit]
    middle = "center" if (not bands["left"] and not bands["right"]) else None
    if not matched:
        return None
    horizontal = next((name for name in ("left", "right") if name in matched), "center")
    vertical = next((name for name in ("top", "bottom") if name in matched), middle or "center")
    if vertical == "center" and horizontal in {"left", "right"}:
        label = f"{horizontal}_center"
    else:
        label = f"{vertical}_{horizontal}" if horizontal != "center" else vertical
    if label not in POSITIONS:
        label = {
            "left_center": "left",
            "right_center": "right",
            "center_center": "center",
            "top_center": "top",
            "bottom_center": "bottom",
        }.get(label, "center")
    if not _validate_slot(label, window_w, window_h, screen_w, screen_h, margin=margin):
        return None
    return label


def _validate_slot(
    label: str, window_w: int, window_h: int, screen_w: int, screen_h: int, *, margin: int
) -> bool:
    """A slot is valid only if the window truly sits inside the screen there."""
    x, y = snap_position(label, window_w, window_h, screen_w, screen_h, margin=margin)
    return 0 <= x <= screen_w - window_w and 0 <= y <= screen_h - window_h


@dataclass
class Question:
    """A quick-choice prompt rendered as tappable chips."""

    title: str
    options: list[str] = field(default_factory=list)


@dataclass
class OrbState:
    """Everything the window needs to draw one frame."""

    energy: str = "idle"
    speaking: bool = False
    look: tuple[float, float] = (0.0, 0.0)
    message: str = ""
    question: Question | None = None

    def apply_energy(self, word: str) -> bool:
        """Switch energies from any recognized word; True when it changed."""
        energy = energy_for_word(word)
        changed = energy != self.energy
        self.energy = energy
        return changed


def load_position(path: Path) -> tuple[int, int] | None:
    """The remembered window position, or None when nothing was saved."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        x, y = int(data["x"]), int(data["y"])
        if x >= 0 and y >= 0:
            return x, y
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return None


def save_position(path: Path, x: int, y: int) -> None:
    """Remember the window position atomically (never corrupt on crash)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"x": int(x), "y": int(y)}), encoding="utf-8")
    os.replace(tmp, path)
