"""Custom vector UI icons and primitives for HANDSHOT (Phase 11). Zero emoji dependencies."""

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
    key_text: str,
    label_text: str,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    cx: float,
    cy: float,
    active: bool = False,
    active_color: tuple[int, int, int] = (255, 220, 80),
) -> pygame.Rect:
    """Render a polished keycap + label unit (e.g. [P] PAUSE)."""
    kw, kh = font.size(key_text)
    lw, lh = small_font.size(label_text) if label_text else (0, 0)

    box_pad_x = 7
    box_w = max(22, kw + box_pad_x * 2)
    box_h = kh + 4

    total_w = box_w + (lw + 6 if label_text else 0)
    start_x = round(cx - total_w / 2)
    start_y = round(cy - box_h / 2)

    # Key box
    box_bg = (30, 46, 70) if active else (18, 28, 44)
    box_border = active_color if active else (50, 75, 110)
    key_col = active_color if active else (220, 235, 255)

    pygame.draw.rect(surface, box_bg, (start_x, start_y, box_w, box_h), border_radius=5)
    pygame.draw.rect(surface, box_border, (start_x, start_y, box_w, box_h), 1, border_radius=5)

    k_surf = font.render(key_text, True, key_col)
    surface.blit(k_surf, k_surf.get_rect(center=(start_x + box_w // 2, start_y + box_h // 2)))

    # Label text
    if label_text:
        lbl_col = active_color if active else (160, 185, 210)
        l_surf = small_font.render(label_text, True, lbl_col)
        surface.blit(l_surf, (start_x + box_w + 6, start_y + (box_h - lh) // 2))

    return pygame.Rect(start_x, start_y, total_w, box_h)


def draw_control_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    typo,
    muted: bool = False,
    debug_on: bool = False,
) -> None:
    """Draw the refined bottom control strip."""
    draw_card(surface, rect, (12, 18, 28, 220), (28, 42, 64), border_width=1, border_radius=8)

    items = [
        ("P", "PAUSE", False, (220, 235, 255)),
        ("R", "RESTART", False, (220, 235, 255)),
        ("M", "MUTED" if muted else "MUTE", muted, (255, 120, 120)),
        ("C", "MIRROR", False, (220, 235, 255)),
        ("D", "DEBUG ON" if debug_on else "DEBUG", debug_on, (255, 220, 80)),
    ]

    spacing = rect.width / (len(items) + 1)
    for i, (key, lbl, is_act, act_col) in enumerate(items, start=1):
        item_cx = rect.left + i * spacing
        draw_keycap(
            surface,
            key,
            lbl,
            typo.small_bold,
            typo.small,
            item_cx,
            rect.centery,
            active=is_act,
            active_color=act_col,
        )


def draw_vector_heart(
    surface: pygame.Surface,
    cx: float,
    cy: float,
    size: float = 16.0,
    active: bool = True,
) -> None:
    """Draw a vector heart icon."""
    fill_col = (255, 65, 90) if active else (38, 24, 32)
    border_col = (255, 140, 160) if active else (70, 42, 55)
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
    pygame.draw.circle(surface, color, (x, y), r, 2)
    pygame.draw.line(surface, color, (x, y - r), (x, y - r - 3), 2)
    pygame.draw.line(surface, color, (x - 3, y - r - 3), (x + 3, y - r - 3), 2)
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
        pygame.draw.line(surface, col, (x + round(r * 0.6), y - round(r * 0.4)), (x + round(r * 1.1), y + round(r * 0.4)), 2)
        pygame.draw.line(surface, col, (x + round(r * 1.1), y - round(r * 0.4)), (x + round(r * 0.6), y + round(r * 0.4)), 2)
    else:
        arc_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.arc(arc_surf, (*col, 220), (0, 0, r * 2, r * 2), -math.pi / 3, math.pi / 3, 2)
        surface.blit(arc_surf, (x - round(r * 0.2), y - r))
