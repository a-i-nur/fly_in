"""Fixed map-domain values for Fly-in."""

from dataclasses import dataclass
from enum import Enum


class ZoneRole(Enum):
    """Identify a zone's role in a map."""

    START = "start"
    END = "end"
    HUB = "hub"


class ZoneType(Enum):
    """Identify a zone's movement rule."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass(frozen=True)
class Zone:
    """Store fixed data and movement facts for one map zone."""

    name: str
    x: int
    y: int
    role: ZoneRole
    zone_type: ZoneType = ZoneType.NORMAL
    color: str = "none"
    max_drones: int = 1

    @property
    def entry_duration(self) -> int:
        """Return the number of turns required to enter this zone."""
        if self.zone_type is ZoneType.RESTRICTED:
            return 2
        return 1

    @property
    def is_blocked(self) -> bool:
        """Return whether this zone cannot be entered."""
        return self.zone_type is ZoneType.BLOCKED


@dataclass(frozen=True)
class Connection:
    """Store one fixed, undirected map connection."""

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    @property
    def key(self) -> tuple[str, str]:
        """Return the canonical identity shared by both endpoint orders."""
        if self.zone_a <= self.zone_b:
            return (self.zone_a, self.zone_b)
        return (self.zone_b, self.zone_a)


class GraphError(ValueError):
    """Describe a structural Graph failure and its offending value."""

    def __init__(
        self,
        reason: str,
        subject: Zone | Connection | ZoneRole | None = None,
    ) -> None:
        """Store the stable cause and value needed for source context."""
        self.reason = reason
        self.subject = subject
        super().__init__(reason)


class Graph:
    """Store fixed zones, connections, and bidirectional adjacency."""

    def __init__(
        self, zones: list[Zone], connections: list[Connection] | None = None
    ) -> None:
        """Build fixed zone and connection storage with terminal references."""
        self._zones: dict[str, Zone] = {}
        self._connections: dict[tuple[str, str], Connection] = {}
        self._adjacent: dict[str, dict[str, Connection]] = {}
        starts: list[Zone] = []
        ends: list[Zone] = []

        for zone in zones:
            if zone.name in self._zones:
                raise GraphError("duplicate zone name", zone)
            self._zones[zone.name] = zone
            self._adjacent[zone.name] = {}

            if zone.role is ZoneRole.START:
                starts.append(zone)
            elif zone.role is ZoneRole.END:
                ends.append(zone)

        if len(starts) != 1:
            raise GraphError(
                "expected exactly one start zone",
                starts[-1] if starts else ZoneRole.START,
            )
        if len(ends) != 1:
            raise GraphError(
                "expected exactly one end zone",
                ends[-1] if ends else ZoneRole.END,
            )

        self._start = starts[0]
        self._end = ends[0]

        if connections is not None:
            for connection in connections:
                if connection.zone_a == connection.zone_b:
                    raise GraphError(
                        "self-connection is not allowed", connection
                    )
                if (
                    connection.zone_a not in self._zones
                    or connection.zone_b not in self._zones
                ):
                    raise GraphError(
                        "connection endpoint is not a zone", connection
                    )
                if connection.key in self._connections:
                    raise GraphError("duplicate connection", connection)

                self._connections[connection.key] = connection
                adjacent_a = self._adjacent[connection.zone_a]
                adjacent_b = self._adjacent[connection.zone_b]
                adjacent_a[connection.zone_b] = connection
                adjacent_b[connection.zone_a] = connection

    @property
    def start(self) -> Zone:
        """Return the fixed start zone."""
        return self._start

    @property
    def end(self) -> Zone:
        """Return the fixed end zone."""
        return self._end

    @property
    def zones(self) -> tuple[Zone, ...]:
        """Return immutable fixed zones without exposing the name registry."""
        return tuple(self._zones.values())

    @property
    def zone_count(self) -> int:
        """Return the number of fixed zones."""
        return len(self._zones)

    @property
    def connection_count(self) -> int:
        """Return the number of fixed connections."""
        return len(self._connections)

    def zone(self, name: str) -> Zone:
        """Return the fixed zone with the supplied name."""
        return self._zones[name]

    def neighbors(self, name: str) -> tuple[str, ...]:
        """Return names of zones joined to the supplied zone."""
        return tuple(self._adjacent[name])

    def connection(self, zone_a: str, zone_b: str) -> Connection:
        """Return the one shared connection between two zones."""
        if zone_a <= zone_b:
            key = (zone_a, zone_b)
        else:
            key = (zone_b, zone_a)
        return self._connections[key]
