"""Abstract Camera Source interface for HANDSHOT (Phase 12)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto

import numpy as np


class CameraSourceType(Enum):
    """Supported video capture hardware sources."""

    LOCAL = auto()
    PHONE = auto()


class CameraSource(ABC):
    """Abstract interface representing a source of video frames."""

    @property
    @abstractmethod
    def source_type(self) -> CameraSourceType:
        """Return LOCAL or PHONE."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of the source (e.g. 'Built-in Webcam', 'Phone Camera')."""

    @property
    @abstractmethod
    def width(self) -> int:
        """Current frame pixel width."""

    @property
    @abstractmethod
    def height(self) -> int:
        """Current frame pixel height."""

    @property
    @abstractmethod
    def mirror(self) -> bool:
        """Whether output frames are horizontally mirrored."""

    @mirror.setter
    @abstractmethod
    def mirror(self, value: bool) -> None:
        """Set horizontal frame mirroring."""

    @property
    @abstractmethod
    def measured_fps(self) -> float:
        """Measured delivery frame rate in FPS."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the source is actively delivering frames."""

    @abstractmethod
    def open(self) -> None:
        """Initialize and open the video stream."""

    @abstractmethod
    def read(self) -> np.ndarray | None:
        """Return the next BGR frame or None if no new frame is available."""

    @abstractmethod
    def release(self) -> None:
        """Close device / stop streaming."""

    @abstractmethod
    def toggle_mirror(self) -> bool:
        """Toggle frame mirroring and return the new state."""

    @abstractmethod
    def describe(self) -> str:
        """Diagnostic summary string."""
