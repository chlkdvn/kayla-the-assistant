"""Draw Kayla's 3D orb: a projected point-sphere, orbit ring, glowing core.

Everything is plain pygame drawing driven by honest 3D math - points live on a
unit sphere, get rotated by a yaw/pitch matrix, and are orthographically
projected with depth-based brightness. No new dependencies, and the geometry
helpers are pure functions the tests can exercise directly.
"""

from __future__ import annotations

import math
from typing import Any

from kayla.orb.state import OrbState

# Style per energy: core color (bright), glow color (bloom), spin speed
# (radians/second), brightness multiplier, and whether the orbit ring shows.
ENERGY_STYLE: dict[str, dict[str, Any]] = {
    "idle": {
        "core": (94, 234, 212),
        "glow": (20, 184, 166),
        "spin": 0.35,
        "breath": 0.9,
        "intensity": 0.55,
        "ring": 0.6,
    },
    "listening": {
        "core": (56, 189, 248),
        "glow": (2, 132, 199),
        "spin": 0.85,
        "breath": 2.1,
        "intensity": 0.85,
        "ring": 1.0,
    },
    "thinking": {
        "core": (167, 139, 250),
        "glow": (109, 40, 217),
        "spin": 1.9,
        "breath": 3.0,
        "intensity": 0.8,
        "ring": 1.0,
    },
    "speaking": {
        "core": (110, 231, 183),
        "glow": (16, 185, 129),
        "spin": 0.95,
        "breath": 3.3,
        "intensity": 1.0,
        "ring": 0.5,
    },
    "working": {
        "core": (251, 191, 36),
        "glow": (217, 119, 6),
        "spin": 1.25,
        "breath": 2.6,
        "intensity": 0.9,
        "ring": 0.8,
    },
    "sleeping": {
        "core": (100, 116, 139),
        "glow": (51, 65, 85),
        "spin": 0.12,
        "breath": 0.35,
        "intensity": 0.22,
        "ring": 0.0,
    },
}

PANEL_TOP = (15, 19, 32)
PANEL_BOTTOM = (6, 8, 14)
PANEL_EDGE = (56, 70, 104)
CHIP_FILL = (30, 41, 59)
CHIP_FILL_HOVER = (51, 65, 85)
CHIP_EDGE = (71, 85, 105)
TEXT_DIM = (148, 163, 184)
TEXT_BRIGHT = (226, 232, 240)

BOTTOM_BAND = 108  # reserved under the orb for the message or question chips
RING_POINTS = 64
SHELL_POINTS = 170


def fibonacci_sphere(count: int) -> list[tuple[float, float, float]]:
    """Evenly distributed unit-sphere points (Rust-like sunflower layout)."""
    golden = math.pi * (3 - math.sqrt(5))
    points: list[tuple[float, float, float]] = []
    for index in range(count):
        y = 1 - (2 * index + 1) / count
        radius = math.sqrt(max(0.0, 1 - y * y))
        theta = golden * index
        points.append((math.cos(theta) * radius, y, math.sin(theta) * radius))
    return points


def rotate_point(
    point: tuple[float, float, float], yaw: float, pitch: float
) -> tuple[float, float, float]:
    """Rotate a unit point: yaw around Y first, then pitch around X."""
    x, y, z = point
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
    x, z = x * cos_yaw - z * sin_yaw, x * sin_yaw + z * cos_yaw
    cos_pitch, sin_pitch = math.cos(pitch), math.sin(pitch)
    y, z = y * cos_pitch - z * sin_pitch, y * sin_pitch + z * cos_pitch
    return x, y, z


def mix(
    dark: tuple[int, int, int], bright: tuple[int, int, int], amount: float
) -> tuple[int, int, int]:
    """Linear color blend."""
    return tuple(  # type: ignore[return-value]
        int(low + (high - low) * amount) for low, high in zip(dark, bright, strict=True)
    )


def _font(size: int):
    """The default bundled font, or None when fonts are unavailable."""
    try:
        import pygame

        if not pygame.font.get_init():
            pygame.font.init()
        return pygame.font.Font(None, size)
    except Exception:  # noqa: BLE001 - text is decoration; the orb must still beat
        return None


class OrbRenderer:
    """Render one orb frame onto a (typically 2x) canvas surface."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        usable = height - BOTTOM_BAND
        self.cx = width // 2
        self.cy = int(usable * 0.52)
        self.radius = max(30, int(min(width, usable) * 0.30))
        self._shell = fibonacci_sphere(SHELL_POINTS)
        self._fonts: dict[int, Any] = {}

    # ------------------------------------------------------------------ draw

    def draw(self, canvas: Any, state: OrbState, t: float, *, hover_chip: int = -1) -> list[Any]:
        """Paint a full frame; returns chip hit-rects at canvas resolution."""

        style = ENERGY_STYLE.get(state.energy, ENERGY_STYLE["idle"])
        breath = 1.0 + 0.05 * math.sin(t * style["breath"])
        intensity = style["intensity"] * (1.15 if state.speaking else 1.0)
        look_x, look_y = state.look
        radius = int(self.radius * breath)

        self._draw_panel(canvas)
        self._draw_glow(canvas, style["glow"], radius, intensity, t, style["breath"])
        if style["ring"] > 0:
            self._draw_ring(canvas, style, radius, t, look_x, intensity)
        self._draw_shell(canvas, style, radius, t, look_x, look_y, intensity)
        self._draw_core(canvas, style, radius, intensity, state.speaking, t)
        if state.speaking:
            self._draw_equalizer(canvas, style, radius, t, look_x, intensity)
        chips = self._draw_band(canvas, state, hover_chip)
        return chips

    def _draw_panel(self, canvas: Any) -> None:
        import pygame

        rect = pygame.Rect(0, 0, self.width, self.height)
        pygame.draw.rect(canvas, PANEL_TOP, rect, border_radius=36)
        gradient = pygame.Rect(0, self.height // 3, self.width, self.height - self.height // 3)
        fade = pygame.Surface(gradient.size, flags=pygame.SRCALPHA)
        fade.fill((*PANEL_BOTTOM, 170))
        canvas.blit(fade, gradient)
        pygame.draw.rect(canvas, PANEL_EDGE, rect, width=1, border_radius=36)

    def _draw_glow(
        self,
        canvas: Any,
        color: tuple[int, int, int],
        radius: int,
        intensity: float,
        t: float,
        breath: float,
    ) -> None:
        import pygame

        pulse = 1.0 + 0.08 * math.sin(t * breath * 1.4)
        for factor, alpha in ((2.05, 16), (1.55, 26), (1.18, 42)):
            glow = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
            pygame.draw.circle(
                glow,
                (*color, int(alpha * min(1.0, intensity + 0.2))),
                (self.cx, self.cy),
                int(radius * factor * pulse),
            )
            canvas.blit(glow, (0, 0))

    def _draw_ring(
        self,
        canvas: Any,
        style: dict[str, Any],
        radius: int,
        t: float,
        look_x: float,
        intensity: float,
    ) -> None:
        import pygame

        center = pygame.Vector2(self.cx, self.cy)
        yaw = t * style["spin"] * 1.5 + look_x * 0.6
        tilt = 0.48
        ring_radius = radius * 1.55
        for index in range(RING_POINTS):
            angle = 2 * math.pi * index / RING_POINTS
            point = (math.cos(angle), 0.0, math.sin(angle))
            x, _y, z = rotate_point(point, yaw, tilt)
            depth = (z + 1) / 2
            position = (
                int(center.x + x * ring_radius),
                int(center.y - 0.0 + z * ring_radius * 0.28),
            )
            alpha = int(40 + 150 * depth) * intensity
            if alpha < 6:
                continue
            size = max(1, int(2.4 * (0.5 + depth)))
            pygame.draw.circle(canvas, (*style["core"], int(min(255, alpha))), position, size)

    def _draw_shell(
        self,
        canvas: Any,
        style: dict[str, Any],
        radius: int,
        t: float,
        look_x: float,
        look_y: float,
        intensity: float,
    ) -> None:
        import pygame

        yaw = t * style["spin"] + look_x * 0.9
        pitch = 0.32 + look_y * 0.8
        shell_radius = radius * 1.18
        bright = mix(style["glow"], (255, 255, 255), 0.35)
        dark = style["glow"]
        for point in self._shell:
            x, y, z = rotate_point(point, yaw, pitch)
            depth = (z + 1) / 2
            alpha = int(18 + 170 * depth) * intensity
            if alpha < 6:
                continue
            position = (
                int(self.cx + x * shell_radius),
                int(self.cy - y * shell_radius),
            )
            size = max(1, int(1.4 + 2.2 * depth))
            pygame.draw.circle(
                canvas, (*mix(dark, bright, depth), int(min(255, alpha))), position, size
            )

    def _draw_core(
        self,
        canvas: Any,
        style: dict[str, Any],
        radius: int,
        intensity: float,
        speaking: bool,
        t: float,
    ) -> None:
        import pygame

        dark = mix(style["glow"], (0, 0, 0), 0.55)
        layers = 16
        for layer in range(layers, 0, -1):
            amount = layer / layers
            layer_radius = int(radius * (0.2 + 0.8 * amount))
            color = mix(dark, style["core"], (amount**1.6) * intensity)
            pygame.draw.circle(canvas, color, (self.cx, self.cy), layer_radius)
        # Specular highlight gives the sphere its rounded, 3D shading.
        highlight = pygame.Surface((self.width, self.height), flags=pygame.SRCALPHA)
        pygame.draw.circle(
            highlight,
            (255, 255, 255, 60),
            (self.cx - radius * 0.34, self.cy - radius * 0.38),
            int(radius * 0.38),
        )
        canvas.blit(highlight, (0, 0))
        pygame.draw.circle(canvas, (*style["core"], 160), (self.cx, self.cy), radius, width=2)

    def _draw_equalizer(
        self,
        canvas: Any,
        style: dict[str, Any],
        radius: int,
        t: float,
        look_x: float,
        intensity: float,
    ) -> None:
        import pygame

        bars = 25
        span = radius * 2.3
        x_start = self.cx - span / 2 + look_x * radius * 0.15
        base = self.cy + radius * 1.5
        bar_width = span / bars
        for index in range(bars):
            wave = (
                math.sin(t * 5.2 + index * 1.7)
                + math.sin(t * 3.1 + index * 0.53)
                + math.sin(t * 8.7 + index * 0.91)
            )
            height = max(3.0, (wave + 1.5) / 3.0 * radius * 0.62 * intensity)
            rect = pygame.Rect(
                int(x_start + index * bar_width),
                int(base - height),
                max(2, int(bar_width * 0.6)),
                int(height),
            )
            pygame.draw.rect(canvas, (*style["core"], 210), rect, border_radius=3)

    # --------------------------------------------------- message/question band

    # Chip text shrinks one notch before we wrap; below the floor chips wrap.
    CHIP_FONT_SIZES = (30, 26)
    TITLE_FONT_SIZES = (36, 28)
    CHIP_HEIGHT = 46
    CHIP_PAD = 26
    CHIP_MIN_WIDTH = 90
    CHIP_GAP = 12
    ROW_GAP = 10
    MAX_CHIP_ROWS = 3

    def question_layout(self, state: OrbState) -> tuple[int | None, list[Any], int]:
        """Geometry for the question band: (title center-y, chip rects, chip font).

        Chips are laid out bottom-anchored and wrap into up to three rows,
        shrinking their font first; a 355-pixel-wide orb then fits "Work mode
        / Focus mode" style chips where one long row used to spill off the
        panel. ``title_y`` centers the title just above the chip block.
        """
        import pygame

        if state.question is None:
            return None, [], self.CHIP_FONT_SIZES[0]
        width_limit = self.width - 40
        for chip_size in self.CHIP_FONT_SIZES:
            font = self._font_at(chip_size)
            if font is None:
                continue
            widths = [
                max(self.CHIP_MIN_WIDTH, font.size(option)[0] + self.CHIP_PAD)
                for option in state.question.options
            ]
            if max(widths, default=0) > width_limit:
                continue  # even one chip cannot fit; try the smaller font
            rows: list[list[pygame.Rect]] = []
            row: list[pygame.Rect] = []
            row_width = 0
            for _option, width in zip(state.question.options, widths, strict=True):
                extra = width + (self.CHIP_GAP if row else 0)
                if row and row_width + extra > width_limit:
                    rows.append(row)
                    row, row_width = [], 0
                    extra = width
                row.append(pygame.Rect(0, 0, width, self.CHIP_HEIGHT))
                row_width += extra
            if row:
                rows.append(row)
            if len(rows) > self.MAX_CHIP_ROWS:
                continue  # too tall; try the smaller font
            band_height = self.CHIP_HEIGHT * len(rows) + self.ROW_GAP * (len(rows) - 1)
            top_y = self.height - 14 - band_height
            chips: list[pygame.Rect] = []
            y = top_y
            for rects in rows:
                total = sum(rect.width for rect in rects) + self.CHIP_GAP * (len(rects) - 1)
                x = (self.width - total) // 2
                for rect in rects:
                    rect.topleft = (x, y)
                    x += rect.width + self.CHIP_GAP
                    chips.append(rect)
                y += self.CHIP_HEIGHT + self.ROW_GAP
            title_font = self._font_at(self._title_font_size())
            title_height = title_font.size("Ag")[1] if title_font is not None else 24
            title_y = max(14, top_y - title_height // 2 - 8)
            return title_y, chips, chip_size
        # No font fits (extreme cases): fall back to the small font, one row,
        # left-aligned so nothing silently disappears.
        font = self._font_at(self.CHIP_FONT_SIZES[-1])
        if font is None:
            return None, [], self.CHIP_FONT_SIZES[-1]
        y = self.height - self.CHIP_HEIGHT - 14
        chips = []
        x = 20
        for option in state.question.options:
            width = font.size(option)[0] + self.CHIP_PAD
            chips.append(pygame.Rect(x, y, width, self.CHIP_HEIGHT))
            x += width + self.CHIP_GAP // 2
        return None, chips, self.CHIP_FONT_SIZES[-1]

    def _draw_band(self, canvas: Any, state: OrbState, hover_chip: int) -> list[Any]:
        """Bottom band: either the status message or the question chips."""

        if state.question is not None:
            return self._draw_question(canvas, state, hover_chip)
        if state.message:
            font = self._font_at(30)
            if font is not None:
                text = self._truncate(font, state.message, self.width - 48)
                canvas.blit(text, text.get_rect(center=(self.width // 2, self.height - 40)))
        return []

    def _title_font_size(self) -> int:
        """The big title fits on a roomy orb; narrow orbs take the small one."""
        return self.TITLE_FONT_SIZES[0] if self.width >= 760 else self.TITLE_FONT_SIZES[-1]

    def _draw_question(self, canvas: Any, state: OrbState, hover_chip: int) -> list[Any]:
        import pygame

        title_y, chips, chip_size = self.question_layout(state)
        if title_y is None or not chips:
            return []
        title_font = self._font_at(self._title_font_size())
        chip_font = self._font_at(chip_size)
        if title_font is None or chip_font is None:
            return []
        title = self._truncate(title_font, state.question.title, self.width - 40, color=TEXT_BRIGHT)
        canvas.blit(title, title.get_rect(center=(self.width // 2, title_y)))
        for index, rect in enumerate(chips):
            hovered = index == hover_chip
            pygame.draw.rect(
                canvas,
                CHIP_FILL_HOVER if hovered else CHIP_FILL,
                rect,
                border_radius=18,
            )
            pygame.draw.rect(canvas, CHIP_EDGE, rect, width=1, border_radius=18)
            label = chip_font.render(state.question.options[index], True, TEXT_BRIGHT)
            canvas.blit(label, label.get_rect(center=rect.center))
        return chips

    def _truncate(self, font: Any, text: str, max_width: int, *, color: Any = TEXT_DIM) -> Any:
        rendered = font.render(text, True, color)
        if rendered.get_width() <= max_width:
            return rendered
        while text and font.render(text + "…", True, color).get_width() > max_width:
            text = text[:-1]
        return font.render(text + "…", True, color)

    def _font_at(self, size: int) -> Any:
        if size not in self._fonts:
            self._fonts[size] = _font(size)
        return self._fonts[size]
