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

    def grid_step_for(self, width: int, height: int) -> float:
        """Select a readable grid interval from the 1, 2, 5 sequence."""
        minimum_x, maximum_x, minimum_y, maximum_y = self._bounds()
        span_x = max(float(maximum_x - minimum_x), 1.0)
        span_y = max(float(maximum_y - minimum_y), 1.0)
        available_width = max(width - 2 * self.PADDING, 1)
        available_height = max(height - 2 * self.PADDING, 1)
        scale = min(available_width / span_x, available_height / span_y)
        target = self.GRID_PIXELS / scale

        for exponent in range(-9, 10):
            magnitude = 10.0 ** exponent
            for factor in (1.0, 2.0, 5.0):
                step = factor * magnitude
                if step >= target:
                    return step
        return 5.0 * 10.0 ** 9

    @classmethod
    def resolve_color(cls, color_name: str) -> Color:
        """Resolve a Pygame color or return the accepted neutral fallback."""
        try:
            color = pygame.Color(color_name)
        except ValueError:
            return cls.FALLBACK_COLOR
        return (color.r, color.g, color.b)

    def _bounds(self) -> tuple[int, int, int, int]:
        """Return the fixed minimum and maximum map coordinates."""
        zones = self._graph.zones
        return (
            min(zone.x for zone in zones),
            max(zone.x for zone in zones),
            min(zone.y for zone in zones),
            max(zone.y for zone in zones),
        )

    def _draw_grid(
        self, surface: pygame.Surface, width: int, height: int
    ) -> None:
        """Draw the faint adaptive coordinate grid behind the graph."""
        minimum_x, maximum_x, minimum_y, maximum_y = self._bounds()
        step = self.grid_step_for(width, height)
        positions = self.screen_positions(width, height)
        reference = self._graph.zones[0]
        reference_x, reference_y = positions[reference.name]
        scale = self.scale_for(width, height)

        for coordinate in self._grid_coordinates(minimum_x, maximum_x, step):
            pixel_x = reference_x + (coordinate - reference.x) * scale
            pygame.draw.line(
                surface, self.GRID_COLOR, (pixel_x, 0), (pixel_x, height)
            )
        for coordinate in self._grid_coordinates(minimum_y, maximum_y, step):
            pixel_y = reference_y - (coordinate - reference.y) * scale
            pygame.draw.line(
                surface, self.GRID_COLOR, (0, pixel_y), (width, pixel_y)
            )

    @staticmethod
    def _grid_coordinates(
        minimum: int, maximum: int, step: float
    ) -> tuple[float, ...]:
        """Return grid coordinates spanning one map axis."""
        first = math.floor(minimum / step)
        last = math.ceil(maximum / step)
        return tuple(index * step for index in range(first, last + 1))

    def _draw_connections(
        self,
        surface: pygame.Surface,
        positions: dict[str, ScreenPoint],
    ) -> None:
        """Draw fixed graph edges without capacity labels."""
        drawn: set[tuple[str, str]] = set()
        for zone in self._graph.zones:
            for neighbor_name in self._graph.neighbors(zone.name):
                key = self._graph.connection(zone.name, neighbor_name).key
                if key not in drawn:
                    pygame.draw.line(
                        surface,
                        self.CONNECTION_COLOR,
                        positions[zone.name],
                        positions[neighbor_name],
                        3,
                    )
                    drawn.add(key)

    def _draw_zones(
        self,
        surface: pygame.Surface,
        positions: dict[str, ScreenPoint],
        result: TurnResult | None,
        drones: tuple[DroneState, ...],
        delivered_count: int,
    ) -> None:
        """Draw fixed zone facts and supplied committed display counts."""
        font = pygame.font.Font(None, 20)
        usage = (
            dict(result.zone_usage)
            if result is not None
            else self._initial_zone_usage(drones)
        )
        for zone in self._graph.zones:
            position = positions[zone.name]
            radius = self._zone_radius(zone)
            pygame.draw.circle(
                surface,
                self.resolve_color(zone.color),
                position,
                radius,
            )
            pygame.draw.circle(
                surface,
                self.LABEL_COLOR,
                position,
                radius,
                4 if zone.role is ZoneRole.START else 2,
            )
            if zone.role is ZoneRole.END:
                pygame.draw.circle(
                    surface,
                    self.LABEL_COLOR,
                    position,
                    radius + 5,
                    2,
                )
            if zone.role in {ZoneRole.START, ZoneRole.END}:
                self._draw_terminal_count(
                    surface,
                    position,
                    self._terminal_count(zone, usage, delivered_count),
                )
            self._draw_zone_text(
                surface,
                font,
                self._shortened_zone_name(font, zone, positions),
                (position[0], position[1] - radius - 14),
            )
            self._draw_zone_text(
                surface,
                font,
                self._shortened_zone_type(font, zone, positions),
                (position[0], position[1] + radius + 12),
            )
            if zone.role not in {ZoneRole.START, ZoneRole.END}:
                self._draw_zone_text(
                    surface,
                    font,
                    self._zone_usage_text(zone, usage),
                    (position[0], position[1] + radius + 30),
                )

    def _draw_terminal_count(
        self,
        surface: pygame.Surface,
        position: ScreenPoint,
        count: int,
    ) -> None:
        """Draw one aggregate waiting or delivered count inside a terminal."""
        font = pygame.font.Font(None, 28)
        label = font.render(str(count), True, self.DRONE_OUTLINE)
        rectangle = label.get_rect(center=position)
        surface.blit(label, rectangle)

    def _shortened_zone_name(
        self,
        font: pygame.font.Font,
        zone: Zone,
        positions: dict[str, ScreenPoint],
    ) -> str:
        """Fit a zone name between nearby zone centers with an ellipsis."""
        return self._shorten_text(
            font, zone.name, self._zone_label_width(zone, positions)
        )

    def _shortened_zone_type(
        self,
        font: pygame.font.Font,
        zone: Zone,
        positions: dict[str, ScreenPoint],
    ) -> str:
        """Fit a zone type below the same dense-map zone gap."""
        return self._shorten_text(
            font,
            zone.zone_type.value,
            self._zone_label_width(zone, positions),
        )

    @staticmethod
    def _zone_label_width(
        zone: Zone, positions: dict[str, ScreenPoint]
    ) -> int:
        """Return the safe horizontal label width around one zone center."""
        nearest = min(
            (
                math.dist(positions[zone.name], position)
                for name, position in positions.items()
                if name != zone.name
            ),
            default=160.0,
        )
        return max(int(nearest) - 8, 16)

    @staticmethod
    def _shorten_text(
        font: pygame.font.Font, text: str, maximum_width: int
    ) -> str:
        """Shorten one label only when its measured width exceeds the gap."""
        if font.size(text)[0] <= maximum_width:
            return text
        ellipsis = "…"
        for end in range(len(text), -1, -1):
            shortened = f"{text[:end]}{ellipsis}"
            if font.size(shortened)[0] <= maximum_width:
                return shortened
        return ellipsis

    @classmethod
    def _zone_radius(cls, zone: Zone) -> int:
        """Return the role-specific radius for one fixed zone."""
        if zone.role is ZoneRole.START:
            return cls.ZONE_RADIUS + 5
        return cls.ZONE_RADIUS

    @staticmethod
    def _initial_zone_usage(
        drones: tuple[DroneState, ...],
    ) -> dict[str, int]:
        """Count only detached pre-turn zone positions for initial display."""
        usage: dict[str, int] = {}
        for drone in drones:
            usage[drone.zone_name] = usage.get(drone.zone_name, 0) + 1
        return usage

    @staticmethod
    def _zone_usage_text(zone: Zone, usage: dict[str, int]) -> str:
        """Format a supplied committed zone-use fact for one fixed zone."""
        count = usage.get(zone.name, 0)
        return f"{count}/{zone.max_drones}"

    def _terminal_count(
        self,
        zone: Zone,
        usage: dict[str, int],
        delivered_count: int,
    ) -> int:
        """Return the supplied aggregate count for one terminal display."""
        if zone.role is ZoneRole.START:
            return usage.get(zone.name, 0)
        if zone.role is ZoneRole.END:
            return delivered_count
        raise ValueError("terminal count requires a start or end zone")

    @staticmethod
    def _draw_zone_text(
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        position: ScreenPoint,
    ) -> None:
        """Draw one zone label at its exact precomputed position."""
        label = font.render(text, True, GraphicalVisualizer.LABEL_COLOR)
        rectangle = label.get_rect(center=position)
        surface.blit(label, rectangle)
