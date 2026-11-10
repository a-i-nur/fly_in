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

    def _prefer_link_wait(
        self,
        drones: tuple[DroneState, ...],
        transits: tuple[TransitState, ...],
        moves: MoveBatch,
        drone: DroneState,
        next_hops: tuple[str, ...],
        safe_hop: str,
    ) -> bool:
        """Compare a conditional one-turn link wait with a safe detour."""
        safe_cost = self._route_cost_from(safe_hop, drone.zone_name)
        assert safe_cost is not None
        for hop in next_hops:
            cost = self._route_cost_from(hop, drone.zone_name)
            assert cost is not None
            if cost[0] + 1 >= safe_cost[0]:
                break
            if not self._destination_has_room(drones, transits, moves, hop):
                continue
            connection = self._graph.connection(drone.zone_name, hop)
            positions = {state.drone_id: state.zone_name for state in drones}
            proposed = [
                destination for drone_id, destination in moves.items()
                if self._graph.connection(
                    positions[drone_id], destination
                ).key == connection.key
            ]
            if any(self._graph.zone(name).entry_duration == 2
                   for name in proposed):
                continue
            usage = len(proposed) + sum(
                transit.connection_key == connection.key
                for transit in transits
            )
            if usage >= connection.max_link_capacity:
                return True
        return False

    def _is_safe_move(
        self,
        drones: tuple[DroneState, ...],
        transits: tuple[TransitState, ...],
        moves: MoveBatch,
        drone: DroneState,
        destination: str,
    ) -> bool:
        """Return whether one move fits current and proposed commitments."""
        connection = self._graph.connection(drone.zone_name, destination)
        drone_positions = {
            current_drone.drone_id: current_drone.zone_name
            for current_drone in drones
        }
        link_use = sum(
            transit.connection_key == connection.key for transit in transits
        )
        link_use += sum(
            self._graph.connection(
                drone_positions[drone_id],
                proposed_destination,
            ).key
            == connection.key
            for drone_id, proposed_destination in moves.items()
        )
        if link_use + 1 > connection.max_link_capacity:
            return False

        return self._destination_has_room(
            drones, transits, moves, destination
        )

    def _destination_has_room(
        self,
        drones: tuple[DroneState, ...],
        transits: tuple[TransitState, ...],
        moves: MoveBatch,
        destination: str,
    ) -> bool:
        """Check destination commitments without forecasting release."""
        if destination in {self._graph.start.name, self._graph.end.name}:
            return True
        destination_occupancy = sum(
            current_drone.zone_name == destination
            and current_drone.drone_id not in moves
            for current_drone in drones
        )
        destination_occupancy += sum(
            proposed_destination == destination
            for proposed_destination in moves.values()
        )
        destination_occupancy += sum(
            transit.destination == destination for transit in transits
        )
        return (
            destination_occupancy + 1
            <= self._graph.zone(destination).max_drones
        )

    def _usable_next_hops(self, origin: str) -> tuple[str, ...]:
        """Return usable first hops in fixed route-preference order."""
        if self._graph.zone(origin).is_blocked:
            return ()
        candidates: list[tuple[int, int, int, str]] = []
        for index, neighbor in enumerate(self._graph.neighbors(origin)):
            if (
                origin != self._graph.start.name
                and neighbor == self._graph.start.name
            ):
                continue
            route_cost = self._route_cost_from(neighbor, origin)
            if route_cost is not None:
                candidates.append((*route_cost, index, neighbor))
        candidates.sort()
        return tuple(candidate[3] for candidate in candidates)

    def _route_cost_from(
        self, first_hop: str, origin: str
    ) -> tuple[int, int] | None:
        """Return the preferred cost from one first hop to the end."""
        first_zone = self._graph.zone(first_hop)
        if first_zone.is_blocked:
            return None
        has_priority = first_zone.zone_type is ZoneType.PRIORITY
        initial_cost = (
            first_zone.entry_duration,
            0 if has_priority else 1,
        )
        paths: list[tuple[int, int, int, str, bool]] = [
            (*initial_cost, 0, first_hop, has_priority)
        ]
        best_costs: dict[str, tuple[int, int]] = {first_hop: initial_cost}
        sequence = 0

        while paths:
            turns, priority_penalty, _, zone_name, path_has_priority = heappop(
                paths
            )
            if best_costs[zone_name] != (turns, priority_penalty):
                continue
            if zone_name == self._graph.end.name:
                return (turns, priority_penalty)
            for neighbor in self._graph.neighbors(zone_name):
                destination = self._graph.zone(neighbor)
                if (
                    neighbor == origin
                    or destination.is_blocked
                    or (
                        origin != self._graph.start.name
                        and neighbor == self._graph.start.name
                    )
                ):
                    continue
                next_has_priority = (
                    path_has_priority
                    or destination.zone_type is ZoneType.PRIORITY
                )
                candidate_cost = (
                    turns + destination.entry_duration,
                    0 if next_has_priority else 1,
                )
                previous_cost = best_costs.get(neighbor)
                if (
                    previous_cost is not None
                    and candidate_cost >= previous_cost
                ):
                    continue
                best_costs[neighbor] = candidate_cost
                sequence += 1
                heappush(
                    paths,
                    (
                        candidate_cost[0],
                        candidate_cost[1],
                        sequence,
                        neighbor,
                        next_has_priority,
                    ),
                )
        return None
