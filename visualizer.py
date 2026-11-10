"""Pygame rendering for committed Fly-in graph movement."""

import math
import os

from model import Graph, Zone, ZoneRole
from simulation import DroneState, TransitState, TurnResult

# Configure the dependency before its first import to preserve movement stdout.
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame  # noqa: E402 -- Pygame reads this setting at import time.


Color = tuple[int, int, int]
ScreenPoint = tuple[float, float]
MovementSegment = tuple[int, ScreenPoint, ScreenPoint]


class GraphicalVisualizer:
    """Draw a fit-to-window view of one fixed graph and its commits."""

    BACKGROUND: Color = (20, 24, 32)
    GRID_COLOR: Color = (53, 60, 72)
    CONNECTION_COLOR: Color = (144, 153, 168)
    LABEL_COLOR: Color = (235, 239, 245)
    FALLBACK_COLOR: Color = (210, 214, 220)
    PADDING = 80
    GRID_PIXELS = 80
    ZONE_RADIUS = 21
    DEFAULT_SIZE = (1200, 800)
    DESKTOP_MARGIN = 80
    DRONE_COLOR: Color = (255, 255, 255)
    DRONE_OUTLINE: Color = (20, 24, 32)
    ANIMATION_STEPS = 6

    def __init__(self, graph: Graph) -> None:
        """Store the fixed graph that this view renders."""
        self._graph = graph
        self._surface: pygame.Surface | None = None
        self._close_requested = False
        self._last_result: TurnResult | None = None
        self._last_drones: tuple[DroneState, ...] = ()
        self._last_transits: tuple[TransitState, ...] = ()
        self._last_delivered_count = 0

    def show(self) -> None:
        """Open the static window until the user closes it."""
        self.open()
        self.wait_for_close()
        self.close()

    def open(
        self,
        drones: tuple[DroneState, ...] = (),
        transits: tuple[TransitState, ...] = (),
        delivered_count: int = 0,
    ) -> None:
        """Open and draw detached initial state without advancing a turn."""
        pygame.init()
        desktops = pygame.display.get_desktop_sizes()
        size = (
            (
                max(1, desktops[0][0] - self.DESKTOP_MARGIN),
                max(1, desktops[0][1] - self.DESKTOP_MARGIN),
            )
            if desktops
            else self.DEFAULT_SIZE
        )
        self._surface = pygame.display.set_mode(
            size, pygame.RESIZABLE
        )
        pygame.display.set_caption("Fly-in map")
        self._last_drones = drones
        self._last_transits = transits
        self._last_delivered_count = delivered_count
        self.draw(
            self._surface,
            drones=drones,
            transits=transits,
            delivered_count=delivered_count,
        )
