"""Hubble Network constellation coverage analysis.

Computes ground tracks, coverage heatmaps, and per-city coverage reports
including gap analysis and revisit time metrics.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .calculator import (
    WGS84_A,
    _ecef_to_geodetic,
    _elevation_from_observer,
    _propagate,
)
from .fetcher import Satellite


@dataclass
class GroundTrackPoint:
    latitude: float
    longitude: float
    altitude_km: float
    timestamp: datetime


@dataclass
class CoverageWindow:
    satellite_name: str
    norad_id: int
    start_time: datetime
    end_time: datetime
    max_elevation_deg: float
    duration_seconds: float


@dataclass
class CityCoverageReport:
    city_name: str
    latitude: float
    longitude: float
    analysis_hours: int
    total_coverage_seconds: float
    coverage_percentage: float
    num_passes: int
    avg_gap_minutes: float
    max_gap_minutes: float
    avg_pass_duration_seconds: float
    windows: list[CoverageWindow] = field(default_factory=list)


def footprint_radius_km(altitude_km: float, min_elevation_deg: float = 10.0) -> float:
    """Ground footprint radius using the geometric relationship between
    Earth radius, satellite altitude, and minimum elevation angle."""
    R = WGS84_A
    theta = math.radians(min_elevation_deg)
    cos_val = R * math.cos(theta) / (R + altitude_km)
    if cos_val >= 1.0:
        return 0.0
    return R * (math.acos(cos_val) - theta)


def compute_ground_tracks(
    satellites: list[Satellite],
    hours: int = 24,
    step_seconds: int = 60,
) -> dict[str, list[GroundTrackPoint]]:
    """Propagate satellites over a time window and return ground track points."""
    now = datetime.now(timezone.utc)
    num_steps = int(hours * 3600 / step_seconds)
    tracks: dict[str, list[GroundTrackPoint]] = {}

    for sat in satellites:
        points: list[GroundTrackPoint] = []
        for i in range(num_steps):
            t = now + timedelta(seconds=i * step_seconds)
            result = _propagate(sat, t)
            if result is None:
                continue
            ecef, _ = result
            lat, lon, alt = _ecef_to_geodetic(*ecef)
            points.append(GroundTrackPoint(
                latitude=round(lat, 4),
                longitude=round(lon, 4),
                altitude_km=round(alt, 1),
                timestamp=t,
            ))
        tracks[sat.name] = points

    return tracks


def compute_city_coverage(
    satellites: list[Satellite],
    city_name: str,
    city_lat: float,
    city_lon: float,
    hours: int = 24,
    step_seconds: int = 30,
    min_elevation_deg: float = 10.0,
) -> CityCoverageReport:
    """Full coverage analysis for a specific ground location.

    Scans at step_seconds intervals, identifies coverage windows where a
    satellite is above min_elevation_deg, and computes gap statistics.
    """
    now = datetime.now(timezone.utc)
    num_steps = int(hours * 3600 / step_seconds)
    windows: list[CoverageWindow] = []

    for sat in satellites:
        in_view = False
        window_start: datetime | None = None
        max_el = 0.0

        for i in range(num_steps):
            t = now + timedelta(seconds=i * step_seconds)
            result = _propagate(sat, t)
            if result is None:
                continue
            ecef, _ = result
            el = _elevation_from_observer(city_lat, city_lon, 0, ecef)

            if el >= min_elevation_deg and not in_view:
                in_view = True
                window_start = t
                max_el = el
            elif el >= min_elevation_deg and in_view:
                max_el = max(max_el, el)
            elif el < min_elevation_deg and in_view:
                in_view = False
                duration = (t - window_start).total_seconds()
                windows.append(CoverageWindow(
                    satellite_name=sat.name,
                    norad_id=sat.norad_id,
                    start_time=window_start,
                    end_time=t,
                    max_elevation_deg=round(max_el, 1),
                    duration_seconds=duration,
                ))

    windows.sort(key=lambda w: w.start_time)

    total_coverage = sum(w.duration_seconds for w in windows)
    total_seconds = hours * 3600
    coverage_pct = (total_coverage / total_seconds) * 100

    gaps: list[float] = []
    if windows:
        first_gap = (windows[0].start_time - now).total_seconds()
        if first_gap > 0:
            gaps.append(first_gap)
        for i in range(1, len(windows)):
            gap = (windows[i].start_time - windows[i - 1].end_time).total_seconds()
            if gap > 0:
                gaps.append(gap)
        end_time = now + timedelta(hours=hours)
        last_gap = (end_time - windows[-1].end_time).total_seconds()
        if last_gap > 0:
            gaps.append(last_gap)
    else:
        gaps.append(float(total_seconds))

    avg_gap = (sum(gaps) / len(gaps) / 60) if gaps else 0
    max_gap = (max(gaps) / 60) if gaps else total_seconds / 60
    avg_pass = (total_coverage / len(windows)) if windows else 0

    return CityCoverageReport(
        city_name=city_name,
        latitude=city_lat,
        longitude=city_lon,
        analysis_hours=hours,
        total_coverage_seconds=total_coverage,
        coverage_percentage=round(coverage_pct, 2),
        num_passes=len(windows),
        avg_gap_minutes=round(avg_gap, 1),
        max_gap_minutes=round(max_gap, 1),
        avg_pass_duration_seconds=round(avg_pass, 1),
        windows=windows,
    )
