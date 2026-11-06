"""Route proposals for currently supported Fly-in paths."""

from heapq import heappop, heappush

from model import Graph, ZoneType
from simulation import DroneState, MoveBatch, TransitState


class PlannerError(ValueError):
    """Describe an exhausted usable-route search."""


