"""Text formatting for committed Fly-in movement results."""

from model import Graph
from simulation import TransitState, TurnResult


class OutputFormatter:
    """Convert committed movement facts into output tokens."""

    def format_turn(self, result: TurnResult) -> str:
        """Return tokens, or an empty string for a committed idle turn."""
        tokens = [
            self._format_transit_departure(transit)
            for transit in result.transit_departures
        ]
        tokens.extend(
            f"D{arrival.drone_id}-{arrival.zone_name}"
            for arrival in result.arrivals
        )
        return " ".join(tokens)

    def format_capacity_info(self, result: TurnResult, graph: Graph) -> str:

        zone_usage = dict(result.zone_usage)
        link_usage = dict(result.link_usage)

        zone = graph.zone(graph.neighbors(graph.start.name)[0])
        connection = graph.connection(graph.start.name, zone.name)

        limit = (
            "unlim"
            if zone in (graph.start, graph.end)
            else str(zone.max_drones)
        )

        zone_used = zone_usage.get(zone.name, 0)
        link_used = link_usage.get(connection.key, 0)

        return (
            f"Zone {zone.name}: {zone_used}/{limit} drones, "
            f"Connection {'-'.join(connection.key)}: "
            f"{link_used}/{connection.max_link_capacity} capacity used"
        )

    def _format_transit_departure(self, transit: TransitState) -> str:
        """Format one ADR-026 travel-direction restricted-transit token."""
        first_endpoint, second_endpoint = transit.connection_key
        source = second_endpoint
        if second_endpoint == transit.destination:
            source = first_endpoint
        return f"D{transit.drone_id}-{source}-{transit.destination}"
