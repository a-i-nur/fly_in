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

