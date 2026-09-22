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
