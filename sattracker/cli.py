"""Command-line interface for satellite tracker."""

import argparse
import sys

from . import display
from .calculator import CITIES, calculate_position, predict_passes
from .fetcher import SATELLITE_GROUPS, fetch_by_group, fetch_by_name, fetch_by_norad_id

HUBBLE_NETWORK_SEARCH = "HUBBLE"
HUBBLE_NETWORK_IDS = {64562, 64565, 64592, 64840}  # HUBBLE 6, LEMUR-2-HUBBLE-4, HUBBLE 7, LEMUR-2-HUBBLE-5


def cmd_track(args: argparse.Namespace) -> None:
    """Track satellites in a CelesTrak group."""
    group = args.group.lower()
    if group not in SATELLITE_GROUPS:
        display.show_error(f"Unknown group '{group}'. Use --list-groups to see available groups.")
        return

    display.show_info(f"Fetching '{group}' satellites from CelesTrak...")
    satellites = fetch_by_group(group)
    if not satellites:
        display.show_error("No satellites found in this group.")
        return

    limit = args.limit or 20
    positions = []
    for sat in satellites[:limit]:
        pos = calculate_position(sat)
        if pos:
            positions.append(pos)

    display.show_positions(positions, title=f"{group.upper()} — {len(positions)} satellites")


def cmd_search(args: argparse.Namespace) -> None:
    """Search for satellites by name."""
    display.show_info(f"Searching for '{args.name}'...")
    satellites = fetch_by_name(args.name)
    if not satellites:
        display.show_error(f"No satellites matching '{args.name}' found.")
        return

    positions = []
    for sat in satellites[:50]:
        pos = calculate_position(sat)
        if pos:
            positions.append(pos)

    display.show_positions(positions, title=f"Search: '{args.name}' — {len(positions)} results")


def cmd_hubble(args: argparse.Namespace) -> None:
    """Track Hubble Network satellites."""
    display.show_info("Fetching Hubble Network satellites...")
    satellites = fetch_by_name(HUBBLE_NETWORK_SEARCH)
    hubble_sats = [s for s in satellites if s.norad_id in HUBBLE_NETWORK_IDS]

    if not hubble_sats:
        display.show_info("Known IDs not found, showing all 'HUBBLE' results:")
        hubble_sats = [s for s in satellites if s.norad_id != 20580]

    positions = []
    for sat in hubble_sats:
        pos = calculate_position(sat)
        if pos:
            positions.append(pos)

    display.show_positions(positions, title=f"Hubble Network — {len(positions)} satellites")


def cmd_passes(args: argparse.Namespace) -> None:
    """Predict satellite passes over a city."""
    city = args.city.lower()
    if city not in CITIES:
        available = ", ".join(CITIES.keys())
        display.show_error(f"Unknown city '{args.city}'. Available: {available}")
        return

    lat, lon = CITIES[city]

    if args.norad_id:
        display.show_info(f"Fetching satellite {args.norad_id}...")
        satellites = fetch_by_norad_id(args.norad_id)
    elif args.name:
        display.show_info(f"Searching for '{args.name}'...")
        satellites = fetch_by_name(args.name)
    else:
        display.show_info("Fetching ISS for pass prediction (use --name or --norad-id for others)...")
        satellites = fetch_by_norad_id(25544)

    if not satellites:
        display.show_error("No satellite found.")
        return

    all_passes = []
    for sat in satellites[:5]:
        display.show_info(f"Calculating passes for {sat.name}...")
        passes = predict_passes(sat, lat, lon, hours=24, min_elevation=args.min_elevation)
        all_passes.extend(passes)

    all_passes.sort(key=lambda p: p.rise_time)
    display.show_passes(all_passes, city)


def cmd_list_groups(_args: argparse.Namespace) -> None:
    """List available satellite groups."""
    display.console.print("\n  [bold]Available satellite groups:[/bold]\n")
    for g in SATELLITE_GROUPS:
        display.console.print(f"    • {g}")
    display.console.print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sattracker",
        description="Real-time satellite tracking powered by CelesTrak + SGP4",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # track
    p_track = subparsers.add_parser("track", help="Track a satellite group")
    p_track.add_argument("group", help="CelesTrak group name (e.g. stations, starlink)")
    p_track.add_argument("-n", "--limit", type=int, default=20, help="Max satellites to display")
    p_track.set_defaults(func=cmd_track)

    # search
    p_search = subparsers.add_parser("search", help="Search satellites by name")
    p_search.add_argument("name", help="Satellite name to search for")
    p_search.set_defaults(func=cmd_search)

    # hubble
    p_hubble = subparsers.add_parser("hubble", help="Track Hubble Network satellites")
    p_hubble.set_defaults(func=cmd_hubble)

    # passes
    p_passes = subparsers.add_parser("passes", help="Predict passes over a city")
    p_passes.add_argument("city", help="City name (e.g. 'tel aviv', 'seattle')")
    p_passes.add_argument("--name", help="Satellite name to search")
    p_passes.add_argument("--norad-id", type=int, help="NORAD catalog number")
    p_passes.add_argument(
        "--min-elevation", type=float, default=10.0, help="Minimum elevation in degrees (default: 10)"
    )
    p_passes.set_defaults(func=cmd_passes)

    # groups
    p_groups = subparsers.add_parser("groups", help="List available satellite groups")
    p_groups.set_defaults(func=cmd_list_groups)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    display.show_banner()
    args.func(args)


if __name__ == "__main__":
    main()
