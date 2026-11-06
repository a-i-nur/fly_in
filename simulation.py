"""Authoritative runtime values for Fly-in simulation."""

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
    