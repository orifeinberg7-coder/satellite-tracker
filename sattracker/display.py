"""Rich terminal display for satellite tracking data."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .calculator import SatPosition, PassPrediction

console = Console()


def _compass(lat: float, lon: float) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}°{ns} {abs(lon):.2f}°{ew}"


def show_positions(positions: list[SatPosition], title: str = "Satellite Positions") -> None:
    """Display satellite positions in a rich table."""
    table = Table(title=title, show_lines=True)
    table.add_column("Satellite", style="bold cyan", min_width=20)
    table.add_column("NORAD ID", justify="right")
    table.add_column("Position", min_width=22)
    table.add_column("Altitude (km)", justify="right", style="green")
    table.add_column("Velocity (km/s)", justify="right", style="yellow")

    for pos in positions:
        table.add_row(
            pos.name,
            str(pos.norad_id),
            _compass(pos.latitude, pos.longitude),
            f"{pos.altitude_km:,.1f}",
            f"{pos.velocity_km_s:.2f}",
        )

    console.print()
    console.print(table)
    if positions:
        console.print(
            f"\n  [dim]Timestamp: {positions[0].timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}[/dim]"
        )
    console.print()


def show_passes(passes: list[PassPrediction], city: str) -> None:
    """Display pass predictions in a rich table."""
    if not passes:
        console.print(f"\n  [yellow]No passes above minimum elevation found for {city}.[/yellow]\n")
        return

    table = Table(title=f"Pass Predictions over {city.title()} (next 24h)", show_lines=True)
    table.add_column("Satellite", style="bold cyan", min_width=20)
    table.add_column("Rise", min_width=12)
    table.add_column("Set", min_width=12)
    table.add_column("Duration", justify="right")
    table.add_column("Max Elevation", justify="right", style="green")
    table.add_column("Peak Time", min_width=12)

    for p in passes:
        mins = int(p.duration_seconds // 60)
        secs = int(p.duration_seconds % 60)
        table.add_row(
            p.satellite_name,
            p.rise_time.strftime("%H:%M:%S"),
            p.set_time.strftime("%H:%M:%S"),
            f"{mins}m {secs}s",
            f"{p.max_elevation_deg:.1f}°",
            p.max_elevation_time.strftime("%H:%M:%S"),
        )

    console.print()
    console.print(table)
    console.print(f"\n  [dim]All times in UTC[/dim]\n")


def show_error(message: str) -> None:
    console.print(f"\n  [bold red]Error:[/bold red] {message}\n")


def show_info(message: str) -> None:
    console.print(f"\n  [bold blue]Info:[/bold blue] {message}\n")


def show_banner() -> None:
    banner = Text()
    banner.append("SATELLITE TRACKER", style="bold white")
    banner.append("  v1.0", style="dim")
    console.print(Panel(banner, subtitle="Powered by CelesTrak + SGP4", border_style="blue"))
