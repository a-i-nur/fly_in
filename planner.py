"""Capacity-aware route schedules for Fly-in fleets."""

from heapq import heappop, heappush

from model import Graph, ZoneType
from simulation import MoveBatch


class PlannerError(ValueError):
    """Describe an exhausted usable-route search."""


class Planner:
    """Reserve complete routes with simultaneous departures and arrivals."""

    def __init__(self, graph: Graph) -> None:
        """Retain the fixed graph used to schedule the fleet."""
        self._graph = graph

    def plan(self, drone_count: int) -> tuple[MoveBatch, ...]:
        """Return one move batch per turn, including forced-arrival turns."""
        zones: dict[tuple[str, int], int] = {}
        links: dict[tuple[str, str, int], int] = {}
        schedule: list[dict[int, str]] = []
        for drone_id in range(1, drone_count + 1):
            # After the last delivery, any simple path takes at most 2V turns.
            deadline = len(schedule) + 2 * self._graph.zone_count
            route = self._route(zones, links, deadline)
            schedule.extend({} for _ in range(route[-1][1] - len(schedule)))
            for (source, turn), (destination, arrival) in zip(
                route, route[1:]
            ):
                if destination not in {
                    self._graph.start.name, self._graph.end.name,
                }:
                    key = (destination, arrival)
                    zones[key] = zones.get(key, 0) + 1
                if source != destination:
                    connection = self._graph.connection(source, destination)
                    link_key = (*connection.key, turn + 1)
                    links[link_key] = links.get(link_key, 0) + 1
                    schedule[turn][drone_id] = destination
        return tuple(schedule)

    def _route(
        self,
        zones: dict[tuple[str, int], int],
        links: dict[tuple[str, str, int], int],
        deadline: int,
    ) -> list[tuple[str, int]]:
        """Find the earliest arrival; prefer priority zones on equal costs."""
        start = self._graph.start
        end = self._graph.end
        if start.is_blocked or end.is_blocked:
            raise PlannerError("no usable route")
        penalty = 0 if start.zone_type is ZoneType.PRIORITY else 1
        paths = [(0, penalty, 0, start.name)]
        best = {(start.name, 0): penalty}
        parents: dict[tuple[str, int], tuple[str, int]] = {}
        sequence = 0

        while paths:
            turn, penalty, _, name = heappop(paths)
            state = (name, turn)
            if best[state] != penalty:
                continue
            if name == end.name:
                route = [state]
                while state in parents:
                    state = parents[state]
                    route.append(state)
                return route[::-1]

            for destination in (*self._graph.neighbors(name), name):
                zone = self._graph.zone(destination)
                if zone.is_blocked:
                    continue
                arrival = turn + (
                    1 if destination == name else zone.entry_duration
                )
                if arrival > deadline:
                    continue
                if (
                    destination not in {start.name, end.name}
                    and zones.get((destination, arrival), 0) >= zone.max_drones
                ):
                    continue
                if destination != name:
                    connection = self._graph.connection(name, destination)
                    # Restricted arrivals release their link in the same turn.
                    if links.get((*connection.key, turn + 1), 0) >= (
                        connection.max_link_capacity
                    ):
                        continue
                next_penalty = (
                    0 if zone.zone_type is ZoneType.PRIORITY else penalty
                )
                next_state = (destination, arrival)
                if best.get(next_state, 2) <= next_penalty:
                    continue
                best[next_state] = next_penalty
                parents[next_state] = state
                sequence += 1
                heappush(paths, (arrival, next_penalty, sequence, destination))
        raise PlannerError("no usable route")
