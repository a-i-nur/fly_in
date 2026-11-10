"""Text formatting for committed Fly-in movement results."""

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

    def _format_transit_departure(self, transit: TransitState) -> str:
        """Format one ADR-026 travel-direction restricted-transit token."""
        first_endpoint, second_endpoint = transit.connection_key
        source = second_endpoint
        if second_endpoint == transit.destination:
            source = first_endpoint
        return f"D{transit.drone_id}-{source}-{transit.destination}"
