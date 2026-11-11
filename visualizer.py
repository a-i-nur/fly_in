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

    def wait_for_step(self) -> bool:
        """Return one request from a Space release, or false when closed."""
        if self._close_requested:
            return False
        while True:
            event = pygame.event.wait()
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.VIDEORESIZE:
                self._resize(event.size)
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                return True

    def wait_for_close(self) -> None:
        """Keep the final committed view visible until the window closes."""
        if self._close_requested:
            return
        while True:
            event = pygame.event.wait()
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.VIDEORESIZE:
                self._resize(event.size)

    def render_committed(
        self,
        result: TurnResult,
        drones: tuple[DroneState, ...],
        transits: tuple[TransitState, ...],
        delivered_count: int,
    ) -> None:
        """Render only the supplied committed movement facts."""
        self._last_result = result
        self._last_drones = drones
        self._last_transits = transits
        self._last_delivered_count = delivered_count
        if self._surface is not None:
            for step in range(self.ANIMATION_STEPS):
                if self._consume_animation_events():
                    return
                surface = self._surface
                if surface is None:
                    return
                self.draw(
                    surface,
                    self.movement_segments(result, *surface.get_size()),
                    step / (self.ANIMATION_STEPS - 1),
                    result,
                    drones,
                    transits,
                    delivered_count,
                )
                pygame.time.wait(40)

    def _consume_animation_events(self) -> bool:
        """Handle close or resize while discarding presentation-time input."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._close_requested = True
                return True
            if event.type == pygame.VIDEORESIZE:
                self._resize(event.size)
        return False

    def close(self) -> None:
        """Release the Pygame window after application execution ends."""
        pygame.quit()
        self._surface = None

    def _resize(self, size: tuple[int, int]) -> None:
        """Recreate and redraw the resizable display surface."""
        self._surface = pygame.display.set_mode(size, pygame.RESIZABLE)
        result = self._last_result
        segments: tuple[MovementSegment, ...] = ()
        if result is not None:
            segments = self.movement_segments(result, *size)
        self.draw(
            self._surface,
            segments,
            result=result,
            drones=self._last_drones,
            transits=self._last_transits,
            delivered_count=self._last_delivered_count,
        )

    def draw(
        self,
        surface: pygame.Surface,
        segments: tuple[MovementSegment, ...] = (),
        progress: float = 1.0,
        result: TurnResult | None = None,
        drones: tuple[DroneState, ...] = (),
        transits: tuple[TransitState, ...] = (),
        delivered_count: int = 0,
    ) -> None:
        """Render the graph at the surface's current size."""
        width, height = surface.get_size()
        positions = self.screen_positions(width, height)
        surface.fill(self.BACKGROUND)
        self._draw_grid(surface, width, height)
        self._draw_connections(surface, positions)
        shown_delivered_count = self._displayed_delivered_count(
            result, delivered_count, progress
        )
        self._draw_zones(
            surface, positions, result, drones, shown_delivered_count
        )
        self._draw_movement(surface, segments, progress, result)
        turn = 0 if result is None else result.turn
        self._draw_turn(surface, f"Turn: {turn}")
        pygame.display.flip()

    def _draw_turn(self, surface: pygame.Surface, text: str) -> None:
        """Draw the sole top-left status line."""
        font = pygame.font.Font(None, 28)
        label = font.render(text, True, self.LABEL_COLOR)
        surface.blit(label, (12, 12))

    def movement_segments(
        self, result: TurnResult, width: int, height: int
    ) -> tuple[MovementSegment, ...]:
        """Return visual paths using only committed movement observations."""
        positions = self.screen_positions(width, height)
        departures = {
            transit.drone_id for transit in result.transit_departures
        }
        arrivals = {transit.drone_id for transit in result.transit_arrivals}
        segments: list[MovementSegment] = []
        for drone_id, source, destination in result.movement_facts:
            source_position = positions[source]
            destination_position = positions[destination]
            midpoint = self._midpoint(source_position, destination_position)
            if drone_id in departures:
                segments.append((drone_id, source_position, midpoint))
            elif drone_id in arrivals:
                segments.append((drone_id, midpoint, destination_position))
            else:
                segments.append(
                    (drone_id, source_position, destination_position)
                )
        return tuple(segments)

    @staticmethod
    def _midpoint(first: ScreenPoint, second: ScreenPoint) -> ScreenPoint:
        """Return the screen midpoint of one committed connection."""
        return ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)

    @staticmethod
    def _interpolate(
        start: ScreenPoint, end: ScreenPoint, progress: float
    ) -> ScreenPoint:
        """Return one presentation position between committed endpoints."""
        return (
            start[0] + (end[0] - start[0]) * progress,
            start[1] + (end[1] - start[1]) * progress,
        )

    def _draw_movement(
        self,
        surface: pygame.Surface,
        segments: tuple[MovementSegment, ...],
        progress: float,
        result: TurnResult | None,
    ) -> None:
        """Draw each committed drone at its presentation-only position."""
        delivered_ids = self._delivered_ids(result)
        for drone_id, start, end in segments:
            if progress >= 1.0 and drone_id in delivered_ids:
                continue
            position = self._interpolate(start, end, progress)
            self._draw_drone(surface, drone_id, position)

    def _displayed_delivered_count(
        self,
        result: TurnResult | None,
        delivered_count: int,
        progress: float,
    ) -> int:
        """Delay a committed goal count until its visual arrivals finish."""
        if progress >= 1.0:
            return delivered_count
        return delivered_count - len(self._delivered_ids(result))

    def _delivered_ids(self, result: TurnResult | None) -> set[int]:
        """Return only identities delivered by this committed result."""
        if result is None:
            return set()
        return {
            drone.drone_id
            for drone in result.arrivals
            if drone.zone_name == self._graph.end.name
        }

    def _draw_drone(
        self,
        surface: pygame.Surface,
        drone_id: int,
        position: ScreenPoint,
    ) -> None:
        """Draw one outlined white drone dot with its readable identity."""
        pygame.draw.circle(surface, self.DRONE_OUTLINE, position, 11)
        pygame.draw.circle(surface, self.DRONE_COLOR, position, 9)
        font = pygame.font.Font(None, 15)
        label = font.render(f"D{drone_id}", True, self.DRONE_OUTLINE)
        rectangle = label.get_rect(center=position)
        surface.blit(label, rectangle)

    def screen_positions(
        self, width: int, height: int
    ) -> dict[str, ScreenPoint]:
        """Return equal-scale, padded screen positions by zone name."""
        minimum_x, maximum_x, minimum_y, maximum_y = self._bounds()
        span_x = max(float(maximum_x - minimum_x), 1.0)
        span_y = max(float(maximum_y - minimum_y), 1.0)
        available_width = max(width - 2 * self.PADDING, 1)
        available_height = max(height - 2 * self.PADDING, 1)
        scale = min(available_width / span_x, available_height / span_y)
        center_x = (minimum_x + maximum_x) / 2
        center_y = (minimum_y + maximum_y) / 2

        return {
            zone.name: (
                width / 2 + (zone.x - center_x) * scale,
                height / 2 - (zone.y - center_y) * scale,
            )
            for zone in self._graph.zones
        }

    def scale_for(self, width: int, height: int) -> float:
        """Return the single world-to-screen scale for a surface size."""
        positions = self.screen_positions(width, height)
        zones = self._graph.zones
        if len(zones) < 2:
            return 1.0
        first = zones[0]
        for zone in zones[1:]:
            delta_x = zone.x - first.x
            if delta_x != 0:
                return abs(
                    (positions[zone.name][0] - positions[first.name][0])
                    / delta_x
                )
            delta_y = zone.y - first.y
            if delta_y != 0:
                return abs(
                    (positions[zone.name][1] - positions[first.name][1])
                    / delta_y
                )
        return 1.0
