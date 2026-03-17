"""AI agent that answers natural language questions using the satellite tracker.

Uses Claude's tool-calling API to route user questions to the right satellite
functions. Claude decides what to call; our code does the actual work.
"""

import json
import os
from pathlib import Path
from typing import Any

import anthropic

def _load_env() -> None:
    """Load .env file from the project root if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

_load_env()
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .calculator import CITIES, calculate_position, predict_passes
from .cli import HUBBLE_NETWORK_IDS
from .coverage import compute_city_coverage
from .fetcher import fetch_by_group, fetch_by_name

console = Console()

MODEL = "claude-haiku-4-5"

# ---------------------------------------------------------------------------
# Tool definitions — this is the "menu" we hand to Claude
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "get_satellite_position",
        "description": (
            "Get the current real-time position of one or more satellites by name. "
            "Returns latitude, longitude, altitude, and velocity for each satellite found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Satellite name or partial name to search for (e.g. 'ISS', 'Starlink', 'HUBBLE').",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of satellites to return. Defaults to 5.",
                    "default": 5,
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "predict_passes",
        "description": (
            "Predict when a satellite will pass over a city in the next 24 hours. "
            "Returns rise time, set time, duration, and max elevation for each pass."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "satellite_name": {
                    "type": "string",
                    "description": "Name of the satellite to look up (e.g. 'ISS', 'HUBBLE').",
                },
                "city": {
                    "type": "string",
                    "description": (
                        f"City to predict passes over. Available: {', '.join(CITIES.keys())}."
                    ),
                },
                "min_elevation_deg": {
                    "type": "number",
                    "description": "Minimum elevation angle in degrees (default 10).",
                    "default": 10,
                },
            },
            "required": ["satellite_name", "city"],
        },
    },
    {
        "name": "track_hubble_constellation",
        "description": (
            "Get the current positions of all Hubble Network satellites. "
            "Hubble Network is building a Bluetooth-to-satellite network using LEO satellites."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "analyze_hubble_coverage",
        "description": (
            "Analyze how well Hubble Network's satellite constellation covers a city. "
            "Returns coverage percentage, number of passes, average gap between passes, "
            "and max gap (worst-case outage window)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": (
                        f"City to analyze coverage for. Available: {', '.join(CITIES.keys())}."
                    ),
                },
                "hours": {
                    "type": "integer",
                    "description": "Analysis window in hours (6, 12, 24, or 48). Defaults to 24.",
                    "default": 24,
                },
                "min_elevation_deg": {
                    "type": "number",
                    "description": "Minimum elevation angle in degrees (default 10).",
                    "default": 10,
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "track_satellite_group",
        "description": (
            "Track all satellites in a named CelesTrak group. "
            "Use this for broad queries like 'show me all Starlink satellites' or 'GPS constellation'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group": {
                    "type": "string",
                    "description": (
                        "CelesTrak group name. Common options: stations, starlink, gps-ops, "
                        "galileo, weather, amateur, cubesat, oneweb."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max satellites to return. Defaults to 10.",
                    "default": 10,
                },
            },
            "required": ["group"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool executor — maps tool names to actual function calls
# ---------------------------------------------------------------------------

def _fetch_hubble_sats():
    all_hubble = fetch_by_name("HUBBLE")
    hubble_sats = [s for s in all_hubble if s.norad_id in HUBBLE_NETWORK_IDS]
    if not hubble_sats:
        hubble_sats = [s for s in all_hubble if s.norad_id != 20580]
    return hubble_sats


def execute_tool(name: str, inputs: dict[str, Any]) -> str:
    """Execute a tool by name and return a JSON string result for Claude."""

    if name == "get_satellite_position":
        sat_name = inputs["name"]
        limit = inputs.get("limit", 5)
        satellites = fetch_by_name(sat_name)
        if not satellites:
            return json.dumps({"error": f"No satellites found matching '{sat_name}'"})
        results = []
        for sat in satellites[:limit]:
            pos = calculate_position(sat)
            if pos:
                results.append({
                    "name": pos.name,
                    "norad_id": pos.norad_id,
                    "latitude": pos.latitude,
                    "longitude": pos.longitude,
                    "altitude_km": pos.altitude_km,
                    "velocity_km_s": pos.velocity_km_s,
                    "timestamp_utc": pos.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                })
        return json.dumps({"satellites": results, "count": len(results)})

    if name == "predict_passes":
        sat_name = inputs["satellite_name"]
        city = inputs["city"].lower()
        min_el = inputs.get("min_elevation_deg", 10)

        if city not in CITIES:
            return json.dumps({"error": f"Unknown city '{city}'. Available: {list(CITIES.keys())}"})

        lat, lon = CITIES[city]
        satellites = fetch_by_name(sat_name)
        if not satellites:
            return json.dumps({"error": f"No satellites found matching '{sat_name}'"})

        all_passes = []
        for sat in satellites[:3]:
            passes = predict_passes(sat, lat, lon, min_elevation=min_el)
            all_passes.extend(passes)
        all_passes.sort(key=lambda p: p.rise_time)

        if not all_passes:
            return json.dumps({
                "city": city,
                "satellite": sat_name,
                "passes": [],
                "message": f"No passes above {min_el}° elevation in the next 24 hours.",
            })

        return json.dumps({
            "city": city,
            "satellite": sat_name,
            "passes": [
                {
                    "satellite_name": p.satellite_name,
                    "rise_utc": p.rise_time.strftime("%H:%M:%S"),
                    "set_utc": p.set_time.strftime("%H:%M:%S"),
                    "peak_utc": p.max_elevation_time.strftime("%H:%M:%S"),
                    "max_elevation_deg": p.max_elevation_deg,
                    "duration_seconds": int(p.duration_seconds),
                }
                for p in all_passes
            ],
            "count": len(all_passes),
        })

    if name == "track_hubble_constellation":
        hubble_sats = _fetch_hubble_sats()
        if not hubble_sats:
            return json.dumps({"error": "Could not find Hubble Network satellites."})
        results = []
        for sat in hubble_sats:
            pos = calculate_position(sat)
            if pos:
                results.append({
                    "name": pos.name,
                    "norad_id": pos.norad_id,
                    "latitude": pos.latitude,
                    "longitude": pos.longitude,
                    "altitude_km": pos.altitude_km,
                    "velocity_km_s": pos.velocity_km_s,
                })
        avg_alt = sum(r["altitude_km"] for r in results) / len(results) if results else 0
        return json.dumps({
            "constellation": "Hubble Network",
            "satellites": results,
            "count": len(results),
            "avg_altitude_km": round(avg_alt, 1),
        })

    if name == "analyze_hubble_coverage":
        city = inputs["city"].lower()
        hours = inputs.get("hours", 24)
        min_el = inputs.get("min_elevation_deg", 10)

        if city not in CITIES:
            return json.dumps({"error": f"Unknown city '{city}'. Available: {list(CITIES.keys())}"})

        lat, lon = CITIES[city]
        hubble_sats = _fetch_hubble_sats()
        if not hubble_sats:
            return json.dumps({"error": "Could not find Hubble Network satellites."})

        report = compute_city_coverage(
            hubble_sats, city, lat, lon,
            hours=hours,
            min_elevation_deg=min_el,
        )
        return json.dumps({
            "city": city,
            "analysis_hours": report.analysis_hours,
            "coverage_percentage": report.coverage_percentage,
            "num_passes": report.num_passes,
            "avg_gap_minutes": report.avg_gap_minutes,
            "max_gap_minutes": report.max_gap_minutes,
            "avg_pass_duration_seconds": report.avg_pass_duration_seconds,
        })

    if name == "track_satellite_group":
        group = inputs["group"].lower()
        limit = inputs.get("limit", 10)
        satellites = fetch_by_group(group)
        if not satellites:
            return json.dumps({"error": f"No satellites found in group '{group}'"})
        results = []
        for sat in satellites[:limit]:
            pos = calculate_position(sat)
            if pos:
                results.append({
                    "name": pos.name,
                    "norad_id": pos.norad_id,
                    "latitude": pos.latitude,
                    "longitude": pos.longitude,
                    "altitude_km": pos.altitude_km,
                    "velocity_km_s": pos.velocity_km_s,
                })
        return json.dumps({"group": group, "satellites": results, "count": len(results)})

    return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Agent — the core loop
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a satellite tracking assistant powered by real-time orbital data.
You have access to tools that can track satellites, predict passes, and analyze constellation coverage.

When answering questions:
- Always use the tools to get live data — never make up satellite positions or pass times.
- Be concise and specific. Users want the key numbers, not a wall of text.
- For coverage analysis, explain what the numbers mean in plain terms (e.g. "a max gap of 90 min means a device could go 90 minutes without connectivity").
- If a city isn't available, tell the user which cities are supported.
"""


def run(user_message: str, api_key: str | None = None) -> str:
    """Run the agent on a single user message and return the final response."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return (
            "ANTHROPIC_API_KEY not set. "
            "Export it with: export ANTHROPIC_API_KEY=sk-ant-..."
        )

    client = anthropic.Anthropic(api_key=key)
    messages: list[dict] = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        # Claude wants to call tools
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                console.print(
                    f"  [dim]→ calling [bold]{block.name}[/bold] "
                    f"with {json.dumps(block.input, separators=(',', ':'))}[/dim]"
                )
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# Interactive chat session
# ---------------------------------------------------------------------------

def chat_session(api_key: str | None = None) -> None:
    """Start an interactive chat loop in the terminal."""
    console.print(
        Panel(
            "[bold white]Satellite AI Agent[/bold white]\n"
            "[dim]Ask anything about satellites, passes, or Hubble Network coverage.\n"
            "Type [bold]exit[/bold] or press Ctrl+C to quit.[/dim]",
            border_style="blue",
        )
    )

    while True:
        try:
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        with console.status("[dim]Thinking…[/dim]", spinner="dots"):
            answer = run(user_input, api_key=api_key)

        console.print("\n[bold green]Agent:[/bold green]")
        console.print(Markdown(answer))
