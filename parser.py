"""Line-level parsing helpers for Fly-in maps."""

from collections.abc import Iterator

from model import Connection, Graph, GraphError, Zone, ZoneRole, ZoneType


class ParseError(ValueError):
    """Describe an input error at a specific source line."""

    def __init__(self, line_number: int, reason: str) -> None:
        """Store the source line and a concise reason for the failure."""
        self.line_number = line_number
        self.reason = reason
        super().__init__(f"Line {line_number}: {reason}")


class MapParser:
    """Parse Fly-in map lines and complete valid maps."""

    def is_comment(self, line: str) -> bool:
        """Return whether a line begins with the comment marker."""
        return line.startswith("#")

    def parse_drone_count(self, line: str, line_number: int) -> int:
        """Parse one positive drone-count declaration."""
        name, separator, value = line.rstrip("\n").partition(":")
        if name != "nb_drones" or not separator:
            raise ParseError(line_number, "expected nb_drones declaration")

        values = value.split()
        if len(values) != 1:
            raise ParseError(line_number, "expected one drone count")

        try:
            drone_count = int(values[0])
        except ValueError as error:
            raise ParseError(
                line_number, "drone count must be an integer"
            ) from error

        if drone_count <= 0:
            raise ParseError(line_number, "drone count must be positive")
        return drone_count

    def parse_zone(self, line: str, line_number: int) -> Zone:
        """Parse one zone declaration and its optional metadata."""
        prefix, separator, value = line.rstrip("\n").partition(":")
        roles = {
            "start_hub": ZoneRole.START,
            "end_hub": ZoneRole.END,
            "hub": ZoneRole.HUB,
        }
        role = roles.get(prefix)
        if not separator or role is None:
            raise ParseError(line_number, "expected a zone declaration")

        fields = value.split()
        if len(fields) < 3:
            raise ParseError(
                line_number, "expected one zone name and two coordinates"
            )
        if (
            len(fields) > 3
            and not fields[3].startswith("[")
            and "=" not in fields[3]
        ):
            raise ParseError(
                line_number, "expected one zone name and two coordinates"
            )

        name, x_value, y_value = fields[:3]
        if "-" in name:
            raise ParseError(line_number, "zone name must not contain dashes")

        try:
            x = int(x_value)
            y = int(y_value)
        except ValueError as error:
            raise ParseError(
                line_number, "zone coordinates must be integers"
            ) from error

        zone_type = ZoneType.NORMAL
        color = "none"
        max_drones = 1

        if len(fields) == 4:
            metadata = fields[3]
        elif len(fields) > 4:
            metadata = " ".join(fields[3:])
        else:
            metadata = ""

        if metadata:
            for key, tag_value in self._metadata_tags(
                metadata,
                line_number,
                "expected one zone name and two coordinates",
                "expected bracketed zone metadata",
                "expected zone metadata",
                "repeated zone metadata key",
            ):
                if key not in {"zone", "color", "max_drones"}:
                    raise ParseError(line_number, "unknown zone metadata key")

                if key == "zone":
                    try:
                        zone_type = ZoneType(tag_value)
                    except ValueError as error:
                        raise ParseError(
                            line_number, "unknown zone type"
                        ) from error
                elif key == "color":
                    color = tag_value
                else:
                    try:
                        max_drones = int(tag_value)
                    except ValueError as error:
                        raise ParseError(
                            line_number, "max_drones must be an integer"
                        ) from error
                    if max_drones <= 0:
                        raise ParseError(
                            line_number, "max_drones must be positive"
                        )

        return Zone(name, x, y, role, zone_type, color, max_drones)

    def parse_connection(self, line: str, line_number: int) -> Connection:
        """Parse one connection declaration and its optional metadata."""
        prefix, separator, value = line.rstrip("\n").partition(":")
        if prefix != "connection" or not separator:
            raise ParseError(line_number, "expected a connection declaration")

        fields = value.split()
        if not fields:
            raise ParseError(line_number, "expected one connection")

        endpoints = fields[0].split("-")
        if len(endpoints) != 2 or not all(endpoints):
            raise ParseError(line_number, "expected two connection endpoints")

        max_link_capacity = 1
        if len(fields) > 1:
            metadata = " ".join(fields[1:])
            for key, tag_value in self._metadata_tags(
                metadata,
                line_number,
                "expected one connection",
                "expected bracketed connection metadata",
                "expected connection metadata",
                "repeated connection metadata key",
            ):
                if key != "max_link_capacity":
                    raise ParseError(
                        line_number, "unknown connection metadata key"
                    )

                try:
                    max_link_capacity = int(tag_value)
                except ValueError as error:
                    raise ParseError(
                        line_number,
                        "max_link_capacity must be an integer",
                    ) from error
                if max_link_capacity <= 0:
                    raise ParseError(
                        line_number,
                        "max_link_capacity must be positive",
                    )

        return Connection(endpoints[0], endpoints[1], max_link_capacity)

    def parse_lines(self, lines: list[str]) -> tuple[Graph, int]:
        """Parse a complete map into its graph and drone count."""
        if not lines:
            raise ParseError(1, "expected nb_drones declaration")

        for count_index, line in enumerate(lines):
            if not line.strip() or self.is_comment(line):
                continue
            drone_count = self.parse_drone_count(line, count_index + 1)
            break
        else:
            raise ParseError(len(lines) + 1, "expected nb_drones declaration")

        zones: list[Zone] = []
        connections: list[Connection] = []
        zone_prefixes = {"start_hub", "end_hub", "hub"}
        defined_zone_names: set[str] = set()
        zone_lines: dict[Zone, int] = {}
        connection_lines: dict[Connection, int] = {}

        for line_number, line in enumerate(
            lines[count_index + 1:], start=count_index + 2
        ):
            if not line.strip() or self.is_comment(line):
                continue

            prefix, _, _ = line.partition(":")
            if prefix in zone_prefixes:
                zone = self.parse_zone(line, line_number)
                zones.append(zone)
                zone_lines[zone] = line_number
                defined_zone_names.add(zone.name)
            elif prefix == "connection":
                connection = self.parse_connection(line, line_number)
                if (
                    connection.zone_a not in defined_zone_names
                    or connection.zone_b not in defined_zone_names
                ):
                    raise ParseError(
                        line_number,
                        "connection endpoint must be defined earlier",
                    )
                connections.append(connection)
                connection_lines[connection] = line_number
            else:
                raise ParseError(
                    line_number, "expected a zone or connection declaration"
                )

        try:
            graph = Graph(zones, connections)
        except GraphError as error:
            line_number = len(lines) + 1
            if isinstance(error.subject, Zone):
                line_number = zone_lines[error.subject]
            elif isinstance(error.subject, Connection):
                line_number = connection_lines[error.subject]
            raise ParseError(line_number, error.reason) from error

        return (graph, drone_count)

    def _metadata_tags(
        self,
        metadata: str,
        line_number: int,
        missing_brackets_reason: str,
        malformed_brackets_reason: str,
        empty_reason: str,
        repeated_key_reason: str,
    ) -> Iterator[tuple[str, str]]:
        """Parse shared metadata syntax without interpreting its values."""
        if not metadata.startswith("[") or not metadata.endswith("]"):
            if "=" not in metadata:
                raise ParseError(line_number, missing_brackets_reason)
            raise ParseError(line_number, malformed_brackets_reason)

        body = metadata[1:-1]
        if "[" in body or "]" in body:
            raise ParseError(line_number, malformed_brackets_reason)

        tags = body.split()
        if not tags:
            raise ParseError(line_number, empty_reason)

        seen_keys: set[str] = set()
        for tag in tags:
            key, separator, value = tag.partition("=")
            if not separator or not key or not value or "=" in value:
                raise ParseError(line_number, "expected metadata key=value")
            if key in seen_keys:
                raise ParseError(line_number, repeated_key_reason)
            seen_keys.add(key)
            yield (key, value)
