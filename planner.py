"""Route proposals for currently supported Fly-in paths."""

from heapq import heappop, heappush

from model import Graph, ZoneType
from simulation import DroneState, MoveBatch, TransitState


class PlannerError(ValueError):
    """Describe an exhausted usable-route search."""


class Planner:
    """Propose safe fleet moves on currently supported paths."""

    def __init__(self, graph: Graph) -> None:
        """Retain the fixed graph used to form move proposals."""
        self._graph = graph

    def propose(
        self,
        drones: tuple[DroneState, ...],
        transits: tuple[TransitState, ...] = (),
    ) -> MoveBatch:
        """Advance safe active drones toward the end."""
        moves: dict[int, str] = {}
        for drone in sorted(drones, key=lambda state: state.drone_id):
            next_hops = self._usable_next_hops(drone.zone_name)
            if not next_hops:
                raise PlannerError("no usable route")
            for next_zone in next_hops:
                if self._is_safe_move(
                    drones, transits, moves, drone, next_zone
                ):
                    if not self._prefer_link_wait(
                        drones, transits, moves, drone, next_hops, next_zone
                    ):
                        moves[drone.drone_id] = next_zone
                    break
        return moves