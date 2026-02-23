"""Orbital mechanics: calculate satellite positions and pass predictions using SGP4."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sgp4.api import Satrec, jday

from .fetcher import Satellite

WGS84_A = 6378.137  # Earth equatorial radius (km)
WGS84_F = 1 / 298.257223563
WGS84_B = WGS84_A * (1 - WGS84_F)
WGS84_E2 = (WGS84_A**2 - WGS84_B**2) / WGS84_A**2

CITIES = {
    "tel aviv": (32.0853, 34.7818),
    "seattle": (47.6062, -122.3321),
    "new york": (40.7128, -74.0060),
    "london": (51.5074, -0.1278),
    "tokyo": (35.6762, 139.6503),
    "san francisco": (37.7749, -122.4194),
}


@dataclass
class SatPosition:
    name: str
    norad_id: int
    latitude: float
    longitude: float
    altitude_km: float
    velocity_km_s: float
    timestamp: datetime


@dataclass
class PassPrediction:
    satellite_name: str
    norad_id: int
    rise_time: datetime
    set_time: datetime
    max_elevation_time: datetime
    max_elevation_deg: float
    duration_seconds: float


def _gmst_degrees(jd_ut1: float) -> float:
    """Greenwich Mean Sidereal Time in degrees (IAU 1982 model)."""
    T = (jd_ut1 - 2451545.0) / 36525.0
    gmst = (
        280.46061837
        + 360.98564736629 * (jd_ut1 - 2451545.0)
        + 0.000387933 * T**2
        - T**3 / 38710000.0
    )
    return gmst % 360.0


def _teme_to_ecef(r_teme: tuple, jd: float, fr: float) -> tuple:
    """Rotate position from TEME to ECEF using GMST."""
    gmst = math.radians(_gmst_degrees(jd + fr))
    cos_g = math.cos(gmst)
    sin_g = math.sin(gmst)
    x = r_teme[0] * cos_g + r_teme[1] * sin_g
    y = -r_teme[0] * sin_g + r_teme[1] * cos_g
    z = r_teme[2]
    return (x, y, z)


def _ecef_to_geodetic(x: float, y: float, z: float) -> tuple:
    """Convert ECEF (km) to geodetic (lat_deg, lon_deg, alt_km) using Bowring's method."""
    lon = math.atan2(y, x)
    p = math.sqrt(x**2 + y**2)
    theta = math.atan2(z * WGS84_A, p * WGS84_B)
    lat = math.atan2(
        z + (WGS84_A**2 - WGS84_B**2) / WGS84_B * math.sin(theta) ** 3,
        p - WGS84_E2 * WGS84_A * math.cos(theta) ** 3,
    )
    sin_lat = math.sin(lat)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat**2)
    if abs(math.cos(lat)) > 1e-10:
        alt = p / math.cos(lat) - N
    else:
        alt = abs(z) - WGS84_B
    return math.degrees(lat), math.degrees(lon), alt


def _geodetic_to_ecef(lat_deg: float, lon_deg: float, alt_km: float = 0) -> tuple:
    """Convert geodetic to ECEF (km)."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat**2)
    x = (N + alt_km) * cos_lat * math.cos(lon)
    y = (N + alt_km) * cos_lat * math.sin(lon)
    z = (N * (1 - WGS84_E2) + alt_km) * sin_lat
    return (x, y, z)


def _elevation_from_observer(
    obs_lat: float, obs_lon: float, obs_alt_km: float, sat_ecef: tuple
) -> float:
    """Calculate elevation angle (degrees) of satellite as seen from observer."""
    obs_ecef = _geodetic_to_ecef(obs_lat, obs_lon, obs_alt_km)
    dx = sat_ecef[0] - obs_ecef[0]
    dy = sat_ecef[1] - obs_ecef[1]
    dz = sat_ecef[2] - obs_ecef[2]

    lat = math.radians(obs_lat)
    lon = math.radians(obs_lon)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)

    # Topocentric South-East-Zenith
    south = sin_lat * cos_lon * dx + sin_lat * sin_lon * dy - cos_lat * dz
    east = -sin_lon * dx + cos_lon * dy
    zenith = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz

    range_km = math.sqrt(south**2 + east**2 + zenith**2)
    if range_km < 1e-10:
        return 90.0
    return math.degrees(math.asin(zenith / range_km))


def _propagate(sat: Satellite, timestamp: datetime) -> tuple | None:
    """Run SGP4 propagation. Returns (ecef_pos, velocity_magnitude) or None on error."""
    satrec = Satrec.twoline2rv(sat.tle_line1, sat.tle_line2)
    jd, fr = jday(
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second + timestamp.microsecond / 1e6,
    )
    error, r_teme, v_teme = satrec.sgp4(jd, fr)
    if error != 0:
        return None
    ecef = _teme_to_ecef(r_teme, jd, fr)
    velocity = math.sqrt(v_teme[0] ** 2 + v_teme[1] ** 2 + v_teme[2] ** 2)
    return ecef, velocity


def calculate_position(sat: Satellite, timestamp: datetime | None = None) -> SatPosition | None:
    """Calculate current lat/lon/alt of a satellite."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    result = _propagate(sat, timestamp)
    if result is None:
        return None
    ecef, velocity = result
    lat, lon, alt = _ecef_to_geodetic(*ecef)
    return SatPosition(
        name=sat.name,
        norad_id=sat.norad_id,
        latitude=round(lat, 4),
        longitude=round(lon, 4),
        altitude_km=round(alt, 1),
        velocity_km_s=round(velocity, 2),
        timestamp=timestamp,
    )


def predict_passes(
    sat: Satellite,
    obs_lat: float,
    obs_lon: float,
    obs_alt_km: float = 0,
    hours: int = 24,
    min_elevation: float = 10.0,
) -> list[PassPrediction]:
    """Predict visible passes of a satellite over an observer within the next N hours.

    Scans at 30-second intervals and groups continuous above-horizon windows.
    Only returns passes where max elevation exceeds min_elevation.
    """
    now = datetime.now(timezone.utc)
    step = timedelta(seconds=30)
    steps = int(hours * 3600 / 30)

    passes: list[PassPrediction] = []
    in_pass = False
    rise_time = None
    max_el = 0.0
    max_el_time = None

    for i in range(steps):
        t = now + step * i
        result = _propagate(sat, t)
        if result is None:
            continue
        ecef, _ = result
        el = _elevation_from_observer(obs_lat, obs_lon, obs_alt_km, ecef)

        if el > 0 and not in_pass:
            in_pass = True
            rise_time = t
            max_el = el
            max_el_time = t
        elif el > max_el and in_pass:
            max_el = el
            max_el_time = t
        elif el <= 0 and in_pass:
            in_pass = False
            if max_el >= min_elevation:
                passes.append(
                    PassPrediction(
                        satellite_name=sat.name,
                        norad_id=sat.norad_id,
                        rise_time=rise_time,
                        set_time=t,
                        max_elevation_time=max_el_time,
                        max_elevation_deg=round(max_el, 1),
                        duration_seconds=(t - rise_time).total_seconds(),
                    )
                )
    return passes
