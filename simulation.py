"""Authoritative runtime values for Fly-in simulation."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from model import Graph

MoveBatch: TypeAlias = Mapping[int, str]
MovementFact: TypeAlias = tuple[int, str, str]
ZoneUsageFact: TypeAlias = tuple[str, int]
LinkUsageFact: TypeAlias = tuple[tuple[str, str], int]


@dataclass(frozen=True)
class DroneState:
    """Identify one active drone at its current zone."""

    drone_id: int
    zone_name: str


@dataclass(frozen=True)
class TransitState:
    """Identify one drone's committed restricted-zone transit."""

    drone_id: int
    connection_key: tuple[str, str]
    destination: str
    due_turn: int


class SimulationError(ValueError):
    """Describe a rejected proposed simulation turn."""


@dataclass(frozen=True)
class TurnResult:
    """Describe all committed movement facts in one turn."""

    turn: int
    arrivals: tuple[DroneState, ...]
    transit_departures: tuple[TransitState, ...] = ()
    movement_facts: tuple[MovementFact, ...] = ()
    transit_arrivals: tuple[TransitState, ...] = ()
    zone_usage: tuple[ZoneUsageFact, ...] = ()
    link_usage: tuple[LinkUsageFact, ...] = ()


class Simulation:
    """Own the committed state of a fleet on a fixed graph."""

    def __init__(self, graph: Graph, drone_count: int = 1) -> None:
        """Place the requested fleet at the graph start before turn one."""
        self._graph = graph
        self._turn = 0
        self._drones = {
            drone_id: DroneState(drone_id, graph.start.name)
            for drone_id in range(1, drone_count + 1)
        }
        self._transits: dict[int, TransitState] = {}
        self._delivered_count = 0

    @property
    def turn(self) -> int:
        """Return the number of committed turns."""
        return self._turn

    @property
    def drones(self) -> tuple[DroneState, ...]:
        """Return immutable active-drone state values."""
        return tuple(self._drones.values())

    @property
    def transits(self) -> tuple[TransitState, ...]:
        """Return immutable restricted-transit state values."""
        return tuple(self._transits.values())

    @property
    def delivered_count(self) -> int:
        """Return the cumulative number of drones delivered so far."""
        return self._delivered_count

    @property
    def is_complete(self) -> bool:
        """Return whether every drone has reached the end."""
        return not self._drones and not self._transits

    def advance(self, moves: MoveBatch) -> TurnResult:
        """Commit one supplied batch and any due transit arrival."""
        if self.is_complete:
            raise SimulationError("simulation is complete")

        for drone_id, destination in moves.items():
            drone = self._drones.get(drone_id)
            if drone is None:
                if drone_id in self._transits:
                    raise SimulationError(f"drone is in transit: {drone_id}")
                raise SimulationError(f"unknown drone id: {drone_id}")
            if self._graph.zone(drone.zone_name).is_blocked:
                raise SimulationError(f"source is blocked: {drone.zone_name}")
            if destination not in self._graph.neighbors(drone.zone_name):
                raise SimulationError(
                    f"destination is not adjacent: {destination}"
                )
            if self._graph.zone(destination).is_blocked:
                raise SimulationError(f"destination is blocked: {destination}")

        occupancy = Counter(
            transit.destination for transit in self._transits.values()
        )
        next_arrivals: Counter[str] = Counter()
        for drone_id, drone in self._drones.items():
            destination = moves.get(drone_id, drone.zone_name)
            if drone_id in moves and (
                self._graph.zone(destination).entry_duration == 2
            ):
                next_arrivals[destination] += 1
            else:
                occupancy[destination] += 1
        for usage in (occupancy, next_arrivals):
            for zone_name, drone_count in usage.items():
                if zone_name in {self._graph.start.name, self._graph.end.name}:
                    continue
                if drone_count > self._graph.zone(zone_name).max_drones:
                    raise SimulationError(
                        f"zone capacity exceeded: {zone_name}"
                    )

        link_use: Counter[tuple[str, str]] = Counter()
        for drone_id, destination in moves.items():
            source = self._drones[drone_id].zone_name
            connection = self._graph.connection(source, destination)
            link_use[connection.key] += 1
        for connection_key, drone_count in link_use.items():
            connection = self._graph.connection(*connection_key)
            if drone_count > connection.max_link_capacity:
                connection_name = "-".join(connection.key)
                raise SimulationError(
                    f"link capacity exceeded: {connection_name}"
                )

        next_drones = self._drones.copy()
        next_transits = self._transits.copy()
        next_delivered_count = self._delivered_count
        arrivals: list[DroneState] = []
        transit_departures: list[TransitState] = []
        movement_facts: list[MovementFact] = []
        transit_arrivals: list[TransitState] = []
        for drone_id, destination in moves.items():
            source = self._drones[drone_id].zone_name
            connection = self._graph.connection(source, destination)
            movement_facts.append((drone_id, source, destination))
            if self._graph.zone(destination).entry_duration == 2:
                transit = TransitState(
                    drone_id,
                    connection.key,
                    destination,
                    self._turn + 2,
                )
                transit_departures.append(transit)
                next_transits[drone_id] = transit
                del next_drones[drone_id]
            else:
                arrival = DroneState(drone_id, destination)
                arrivals.append(arrival)
                if destination == self._graph.end.name:
                    del next_drones[drone_id]
                    next_delivered_count += 1
                else:
                    next_drones[drone_id] = arrival

        for drone_id, transit in self._transits.items():
            if transit.due_turn != self._turn + 1:
                continue
            arrival = DroneState(drone_id, transit.destination)
            arrivals.append(arrival)
            first_endpoint, second_endpoint = transit.connection_key
            source = (
                second_endpoint
                if first_endpoint == transit.destination
                else first_endpoint
            )
            movement_facts.append((drone_id, source, transit.destination))
            transit_arrivals.append(transit)
            del next_transits[drone_id]
            if transit.destination != self._graph.end.name:
                next_drones[drone_id] = arrival
            else:
                next_delivered_count += 1

        self._drones = next_drones
        self._transits = next_transits
        self._delivered_count = next_delivered_count
        self._turn += 1
        zone_use = Counter(drone.zone_name for drone in next_drones.values())
        return TurnResult(
            self._turn,
            tuple(arrivals),
            tuple(transit_departures),
            tuple(movement_facts),
            tuple(transit_arrivals),
            tuple(sorted(zone_use.items())),
            tuple(sorted(link_use.items())),
        )
