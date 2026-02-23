# Satellite Tracker

Real-time satellite tracking tool built with Python. Fetches live orbital data from [CelesTrak](https://celestrak.org/), calculates positions using SGP4 propagation (the same algorithm NASA uses), and displays results in a clean terminal UI or interactive web dashboard.

**Special focus on [Hubble Network](https://hubblenetwork.com/) satellites** — tracking the constellation that's bringing Bluetooth connectivity from space.

## Features

- **Live satellite tracking** — real-time lat/lon/altitude for any satellite in orbit
- **Search** — find any satellite by name or NORAD catalog ID
- **Hubble Network mode** — dedicated tracking for Hubble Network's satellite constellation
- **Pass predictions** — calculate when satellites pass over Tel Aviv, Seattle, and other cities
- **Web dashboard** — interactive map visualization with Streamlit + Folium
- **CLI interface** — clean terminal output with Rich tables

## Quick Start

```bash
# Clone the repo
git clone https://github.com/orifeinberg7-coder/satellite-tracker.git
cd satellite-tracker

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the CLI
python -m sattracker track stations
python -m sattracker hubble
python -m sattracker passes "tel aviv"

# Run the web dashboard
streamlit run app.py
```

## CLI Commands

```bash
# Track a satellite group (e.g. stations, starlink, weather)
python -m sattracker track stations

# Search for a satellite by name
python -m sattracker search "ISS"

# Track Hubble Network satellites
python -m sattracker hubble

# Predict ISS passes over Tel Aviv
python -m sattracker passes "tel aviv"

# Predict passes for a specific satellite over Seattle
python -m sattracker passes "seattle" --name "HUBBLE 6"

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
3. **Transform** — TEME coordinates → ECEF → geodetic (lat/lon/alt)
4. **Display** — Rich tables in terminal, or Folium maps in web dashboard

## Project Structure

```
satellite-tracker/
├── README.md
├── requirements.txt
├── app.py                  # Streamlit web dashboard
└── sattracker/
    ├── __init__.py
    ├── __main__.py         # python -m entry point
    ├── cli.py              # CLI commands and argument parsing
    ├── fetcher.py          # CelesTrak API client
    ├── calculator.py       # SGP4 orbital mechanics
    └── display.py          # Rich terminal formatting
```

## Author

**Ori Feinberg** — [github.com/orifeinberg7-coder](https://github.com/orifeinberg7-coder)
