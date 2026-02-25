# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Satellite Tracker — a Python app for real-time satellite tracking using CelesTrak public API + SGP4 orbital mechanics. Two interfaces: Streamlit web dashboard (`app.py`) and CLI (`python3 -m sattracker`). No database, no secrets, no Docker.

### Running the app

- **Web dashboard**: `streamlit run app.py --server.port 8501 --server.headless true`
- **CLI**: `python3 -m sattracker <command>` (e.g., `groups`, `search "ISS"`, `hubble`, `coverage "tel aviv"`, `passes "tel aviv"`)
- See `README.md` for full CLI command reference.

### Testing

- `pytest` is listed in `requirements.txt` but no test files exist yet. Run `python3 -m pytest` to execute any tests added in the future.
- No linter is configured in the project.

### Caveats

- Use `python3` not `python` — the VM does not have `python` on PATH.
- pip installs to `~/.local/bin` by default (user install). Ensure `~/.local/bin` is on PATH for `streamlit`, `pytest`, etc.
- All data comes from the CelesTrak public API; internet access is required for any functionality.
