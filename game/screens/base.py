"""Base Screen interface for Handshot UI state management."""

from __future__ import annotations

import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.aim_screen import AimScreen
    from gestures import PinchResult, ReloadResult
    from camera.hand_tracker import TrackingResult

class Screen:
    """Base class for all application screens/states."""

    def __init__(self, app: AimScreen) -> None:
        self.app = app

    def handle_key_event(self, event: pygame.event.Event, now: float) -> bool:
        """Handle keyboard input specific to this screen. Return True if handled."""
        return False

    def update(self, delta_seconds: float, has_hand: bool, now: float) -> None:
        """Update simulation/logic for this screen."""
        pass

    def draw(
        self,
        surface: pygame.Surface,
        result: TrackingResult | None,
        pinch_result: PinchResult | None,
        reload_result: ReloadResult | None,
        aim_pos: tuple[float, float],
        now: float,
    ) -> None:
        """Render the screen's visual elements."""
        pass
