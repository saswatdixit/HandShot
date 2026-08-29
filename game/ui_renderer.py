"""Custom vector UI icons and primitives for HANDSHOT (Phase 10.5). Zero emoji dependencies."""

from __future__ import annotations

import math
import pygame


def draw_card(
    surface: pygame.Surface,
    rect: tuple[int, int, int, int] | pygame.Rect,
    bg_color: tuple[int, int, int] | tuple[int, int, int, int],
    border_color: tuple[int, int, int] | tuple[int, int, int, int] | None = None,
    border_width: int = 1,
    border_radius: int = 12,
) -> pygame.Rect:
    """Draw a clean rounded card panel with optional alpha and border."""
    x, y, w, h = rect
    r = pygame.Rect(x, y, w, h)
    card_surf = pygame.Surface((w, h), pygame.SRCALPHA)

    bg_alpha = bg_color[3] if len(bg_color) == 4 else 255
    pygame.draw.rect(card_surf, (*bg_color[:3], bg_alpha), (0, 0, w, h), border_radius=border_radius)

    if border_color is not None and border_width > 0:
        b_alpha = border_color[3] if len(border_color) == 4 else 255
        pygame.draw.rect(
            card_surf, (*border_color[:3], b_alpha), (0, 0, w, h), border_width, border_radius=border_radius
        )

    surface.blit(card_surf, (x, y))
    return r


def draw_keycap(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    cx: float,
    cy: float,
    text_color: tuple[int, int, int] = (220, 235, 255),
    bg_color: tuple[int, int, int] = (22, 34, 52),
    border_color: tuple[int, int, int] = (60, 90, 130),
) -> pygame.Rect:
    """Render an arcade keycap button pill."""
    txt_w, txt_h = font.size(text)
    pad_x, pad_y = 10, 4
    w = max(26, txt_w + pad_x * 2)
    h = txt_h + pad_y * 2
    x = round(cx - w / 2)
    y = round(cy - h / 2)

    pygame.draw.rect(surface, bg_color, (x, y, w, h), border_radius=6)
    pygame.draw.rect(surface, border_color, (x, y, w, h), 1, border_radius=6)

    txt_surf = font.render(text, True, text_color)
    surface.blit(txt_surf, txt_surf.get_rect(center=(round(cx), round(cy))))
    return pygame.Rect(x, y, w, h)


def draw_vector_heart(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    size: float = 18.0,
    active: bool = True,
) -> None:
    """Draw a vector heart icon."""
    fill_col = (255, 65, 90) if active else (40, 25, 35)
    border_col = (255, 140, 160) if active else (75, 45, 60)
    s = size / 18.0

    pts = [
        (cx, cy + 8 * s),
        (cx - 8 * s, cy - 1 * s),
        (cx - 8 * s, cy - 6 * s),
        (cx - 4 * s, cy - 9 * s),
        (cx, cy - 5 * s),
        (cx + 4 * s, cy - 9 * s),
        (cx + 8 * s, cy - 6 * s),
        (cx + 8 * s, cy - 1 * s),
    ]
    pygame.draw.polygon(surface, fill_col, pts)
    pygame.draw.polygon(surface, border_col, pts, 1)


def draw_vector_stopwatch(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float = 10.0,
    color: tuple[int, int, int] = (255, 215, 80),
) -> None:
    """Draw a vector stopwatch icon."""
    x, y, r = round(cx), round(cy), round(radius)
    # Outer circle
    pygame.draw.circle(surface, color, (x, y), r, 2)
    # Top knob
    pygame.draw.line(surface, color, (x, y - r), (x, y - r - 3), 2)
    pygame.draw.line(surface, color, (x - 3, y - r - 3), (x + 3, y - r - 3), 2)
    # Clock hands
    pygame.draw.line(surface, color, (x, y), (x, y - round(r * 0.6)), 2)
    pygame.draw.line(surface, color, (x, y), (x + round(r * 0.45), y), 2)


def draw_vector_target(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float = 10.0,
    color: tuple[int, int, int] = (110, 235, 150),
) -> None:
    """Draw a vector bullseye target icon."""
    x, y, r = round(cx), round(cy), round(radius)
    pygame.draw.circle(surface, color, (x, y), r, 2)
    pygame.draw.circle(surface, color, (x, y), max(2, round(r * 0.45)), 1)
    pygame.draw.circle(surface, color, (x, y), 2)


def draw_vector_leaf(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float = 10.0,
    color: tuple[int, int, int] = (105, 245, 160),
) -> None:
    """Draw a vector chill leaf icon."""
    x, y, r = round(cx), round(cy), round(radius)
    pts = [
        (x, y - r),
        (x + r, y - round(r * 0.3)),
        (x + round(r * 0.5), y + round(r * 0.8)),
        (x, y + r),
        (x - round(r * 0.5), y + round(r * 0.8)),
        (x - r, y - round(r * 0.3)),
    ]
    pygame.draw.polygon(surface, color, pts, 2)
    pygame.draw.line(surface, color, (x, y - r), (x, y + r), 1)


def draw_vector_star(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float = 12.0,
    color: tuple[int, int, int] = (255, 220, 80),
) -> None:
    """Draw a 5-point vector star icon."""
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * (math.pi / 5)
        r = radius if i % 2 == 0 else radius * 0.45
        pts.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    pygame.draw.polygon(surface, color, pts)


def draw_vector_speaker(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    radius: float = 9.0,
    muted: bool = False,
    color: tuple[int, int, int] = (130, 220, 255),
) -> None:
    """Draw a vector speaker icon with mute cross."""
    x, y, r = round(cx), round(cy), round(radius)
    col = (255, 110, 110) if muted else color

    pts = [
        (x - round(r * 0.7), y - round(r * 0.4)),
        (x - round(r * 0.2), y - round(r * 0.4)),
        (x + round(r * 0.3), y - round(r * 0.8)),
        (x + round(r * 0.3), y + round(r * 0.8)),
        (x - round(r * 0.2), y + round(r * 0.4)),
        (x - round(r * 0.7), y + round(r * 0.4)),
    ]
    pygame.draw.polygon(surface, col, pts)

    if muted:
        # X cross
        pygame.draw.line(surface, col, (x + round(r * 0.6), y - round(r * 0.4)), (x + round(r * 1.1), y + round(r * 0.4)), 2)
        pygame.draw.line(surface, col, (x + round(r * 1.1), y - round(r * 0.4)), (x + round(r * 0.6), y + round(r * 0.4)), 2)
    else:
        # Sound arc
        arc_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.arc(arc_surf, (*col, 220), (0, 0, r * 2, r * 2), -math.pi / 3, math.pi / 3, 2)
        surface.blit(arc_surf, (x - round(r * 0.2), y - r))
