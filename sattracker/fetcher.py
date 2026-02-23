"""Fetch and parse TLE satellite data from CelesTrak."""

from dataclasses import dataclass

import requests

CELESTRAK_BASE = "https://celestrak.org/NORAD/elements/gp.php"

SATELLITE_GROUPS = [
    "stations",
    "visual",
    "active",
    "analyst",
    "weather",
    "noaa",
    "resource",
    "sarsat",
    "dmc",
    "tdrss",
    "argos",
    "intelsat",
    "ses",
    "iridium",
    "iridium-NEXT",
    "starlink",
    "oneweb",
    "orbcomm",
    "globalstar",
    "amateur",
    "gps-ops",
    "galileo",
    "beidou",
    "gnss",
    "geo",
    "science",
    "geodetic",
    "engineering",
    "education",
    "military",
    "radar",
    "cubesat",
    "last-30-days",
]


@dataclass
class Satellite:
    name: str
    norad_id: int
    tle_line1: str
    tle_line2: str


def parse_tle_text(tle_text: str) -> list[Satellite]:
    """Parse raw TLE-format text into Satellite objects.

    TLE format has 3-line groups: name, line1 (starts with '1'), line2 (starts with '2').
    """
    lines = [line.strip() for line in tle_text.strip().split("\n") if line.strip()]
    satellites = []
    i = 0
    while i < len(lines) - 2:
        if not lines[i].startswith("1 ") and not lines[i].startswith("2 "):
            name = lines[i]
            line1 = lines[i + 1]
            line2 = lines[i + 2]
            if line1.startswith("1 ") and line2.startswith("2 "):
                norad_id = int(line1[2:7].strip())
                satellites.append(
                    Satellite(
                        name=name,
                        norad_id=norad_id,
                        tle_line1=line1,
                        tle_line2=line2,
                    )
                )
                i += 3
                continue
        i += 1
    return satellites


def fetch_by_group(group: str) -> list[Satellite]:
    """Fetch all satellites in a CelesTrak group (e.g. 'stations', 'starlink')."""
    resp = requests.get(CELESTRAK_BASE, params={"GROUP": group, "FORMAT": "tle"}, timeout=30)
    resp.raise_for_status()
    return parse_tle_text(resp.text)


def fetch_by_name(name: str) -> list[Satellite]:
    """Search for satellites by name (partial match)."""
    resp = requests.get(CELESTRAK_BASE, params={"NAME": name, "FORMAT": "tle"}, timeout=30)
    resp.raise_for_status()
    return parse_tle_text(resp.text)


def fetch_by_norad_id(norad_id: int) -> list[Satellite]:
    """Fetch a specific satellite by its NORAD catalog number."""
    resp = requests.get(CELESTRAK_BASE, params={"CATNR": norad_id, "FORMAT": "tle"}, timeout=30)
    resp.raise_for_status()
    return parse_tle_text(resp.text)
