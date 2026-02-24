# Satellite Tracker

Real-time satellite tracking and constellation coverage analysis, with a special focus on **[Hubble Network](https://hubblenetwork.com/)** — the company building the world's first Bluetooth-to-satellite network.

Built with Python, SGP4 orbital mechanics, and Streamlit.

## Why Hubble Network?

Hubble Network is deploying a constellation of LEO satellites that connect directly to standard Bluetooth chips — enabling billions of devices to communicate from anywhere on Earth without cellular infrastructure. This tool tracks their constellation in real-time and analyzes global coverage patterns, including revisit times and per-city gap analysis.

## Features

### Real-Time Tracking
- Track any satellite group (ISS, Starlink, GPS, weather, etc.) using live CelesTrak data
- Search satellites by name or NORAD catalog ID
- Interactive world map with satellite positions, altitude, and velocity

### Hubble Network Dashboard
- Dedicated tracking for Hubble Network's satellite constellation
- Real-time position and orbital data for all Hubble satellites
- City markers for Tel Aviv and Seattle

### Constellation Coverage Analysis
- **Ground track visualization** — orbital paths with per-satellite color coding
- **Coverage heatmap** — global density map showing where the constellation provides the most coverage
- **Per-city analysis** — coverage percentage, pass count, and gap analysis
- **Revisit time metrics** — max gap between passes, average gap, average pass duration
- Toggle between ground tracks and heatmap layers

### Pass Predictions
- Calculate when satellites pass over Tel Aviv, Seattle, New York, and more
- Configurable minimum elevation angle
- Duration and peak elevation for each pass

## Quick Start

```bash
git clone https://github.com/orifeinberg7-coder/satellite-tracker.git
cd satellite-tracker

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Web dashboard
streamlit run app.py

# CLI
python -m sattracker hubble
python -m sattracker coverage "tel aviv"
python -m sattracker passes "seattle" --name "HUBBLE"
```

## CLI Commands

```bash
# Track a satellite group
python -m sattracker track stations

# Search for a satellite by name
python -m sattracker search "ISS"

# Track Hubble Network satellites
python -m sattracker hubble

# Analyze Hubble coverage over Tel Aviv (24h)
python -m sattracker coverage "tel aviv"

# Analyze coverage with custom window and elevation
python -m sattracker coverage "seattle" --hours 48 --min-elevation 15

# Predict ISS passes over Tel Aviv
python -m sattracker passes "tel aviv"

# Predict Hubble passes over Seattle
python -m sattracker passes "seattle" --name "HUBBLE"

# List all available satellite groups
python -m sattracker groups
```

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3 |
| Orbital mechanics | SGP4 (NORAD standard propagator) |
| Data source | CelesTrak public API |
| Terminal UI | Rich |
| Web dashboard | Streamlit |
| Map visualization | Folium |

## How It Works

1. **Fetch** — TLE (Two-Line Element) data from CelesTrak's public API
2. **Propagate** — SGP4 algorithm computes satellite position at any point in time
3. **Transform** — TEME → ECEF → geodetic coordinate conversion (WGS84)
4. **Analyze** — Coverage windows, gap analysis, and revisit time calculations
5. **Display** — Rich tables in terminal, Folium maps + Streamlit in browser

## Project Structure

```
satellite-tracker/
├── README.md
├── requirements.txt
├── app.py                  # Streamlit web dashboard
└── sattracker/
    ├── __init__.py
    ├── __main__.py         # python -m entry point
    ├── cli.py              # CLI commands
    ├── fetcher.py          # CelesTrak API client
    ├── calculator.py       # SGP4 orbital mechanics
    ├── coverage.py         # Constellation coverage analysis
    └── display.py          # Rich terminal formatting
```

## Author

**Ori Feinberg** — [github.com/orifeinberg7-coder](https://github.com/orifeinberg7-coder)
