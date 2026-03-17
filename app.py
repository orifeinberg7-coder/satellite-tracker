"""Streamlit web dashboard for satellite tracking and coverage analysis."""

import folium
import streamlit as st
from folium import FeatureGroup
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from sattracker.calculator import CITIES, calculate_position
from sattracker.cli import HUBBLE_NETWORK_IDS
from sattracker.coverage import compute_city_coverage, compute_ground_tracks
from sattracker.fetcher import SATELLITE_GROUPS, fetch_by_group, fetch_by_name

st.set_page_config(page_title="Satellite Tracker", page_icon="🛰️", layout="wide")

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ---------- globals ---------- */
    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif;
    }
    .block-container {
        padding: 2rem 2.5rem 2rem 2.5rem;
        max-width: 1280px;
    }

    /* ---------- header ---------- */
    .app-header {
        text-align: center;
        padding: 2.2rem 0 1.4rem 0;
    }
    .app-header h1 {
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin: 0;
    }
    .app-header .tagline {
        font-size: 0.95rem;
        opacity: 0.55;
        margin-top: 0.3rem;
    }
    .app-header .divider {
        width: 64px;
        height: 3px;
        border-radius: 3px;
        background: linear-gradient(90deg, #6366f1, #818cf8);
        margin: 0.9rem auto 0 auto;
    }

    /* ---------- tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        justify-content: center;
        border-bottom: 1px solid rgba(128,128,128,.15);
        padding-bottom: 0;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.88rem;
        font-weight: 500;
        padding: 0.65rem 1.5rem;
        border-radius: 8px 8px 0 0;
        border: none;
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 2.5px solid #6366f1 !important;
        color: #6366f1 !important;
    }

    /* ---------- control panel ---------- */
    .control-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        opacity: 0.45;
        margin-bottom: 0.1rem;
    }

    /* ---------- metrics ---------- */
    [data-testid="stMetric"] {
        background: rgba(99,102,241,.06);
        border: 1px solid rgba(99,102,241,.12);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.72rem !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        opacity: 0.5;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }

    /* ---------- dataframes ---------- */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* ---------- buttons ---------- */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.82rem;
        padding: 0.55rem 1rem;
        transition: all 0.15s ease;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #818cf8);
        border: none;
        color: white;
    }

    /* ---------- section ---------- */
    .section-heading {
        font-size: 1.1rem;
        font-weight: 600;
        margin: 1.5rem 0 0.8rem 0;
    }
    .section-description {
        font-size: 0.88rem;
        opacity: 0.55;
        line-height: 1.55;
        margin-bottom: 1.2rem;
    }

    /* ---------- stat card ---------- */
    .stat-card {
        background: rgba(99,102,241,.06);
        border: 1px solid rgba(99,102,241,.10);
        border-radius: 12px;
        padding: 1.1rem 1.3rem;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .stat-card .value {
        font-size: 1.85rem;
        font-weight: 700;
    }
    .stat-card .label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        opacity: 0.45;
        margin-top: 0.15rem;
    }

    /* ---------- empty state ---------- */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        opacity: 0.45;
    }
    .empty-state .icon { font-size: 2.4rem; margin-bottom: 0.5rem; }
    .empty-state .msg  { font-size: 0.88rem; }

    /* ---------- misc ---------- */
    hr { opacity: 0.12; margin: 1.5rem 0; }

    /* hide streamlit hamburger & footer */
    #MainMenu, footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
        <h1>🛰️&ensp;Satellite Tracker</h1>
        <div class="tagline">Real-time tracking &amp; coverage analysis &middot; Powered by CelesTrak + SGP4</div>
        <div class="divider"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAT_COLORS = [
    "#818cf8", "#f472b6", "#34d399", "#fbbf24",
    "#60a5fa", "#fb923c", "#a78bfa",
]

CITY_DISPLAY = {k: k.title() for k in CITIES}

MAP_TILES = "CartoDB dark_matter"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_hubble_sats():
    """Fetch Hubble Network satellites, falling back to name search."""
    all_hubble = fetch_by_name("HUBBLE")
    hubble_sats = [s for s in all_hubble if s.norad_id in HUBBLE_NETWORK_IDS]
    if not hubble_sats:
        hubble_sats = [s for s in all_hubble if s.norad_id != 20580]
    return hubble_sats


def _make_popup_html(lines: list[tuple[str, str]]) -> str:
    rows = "".join(
        f'<tr><td style="opacity:.6;padding:2px 8px 2px 0;font-size:12px">{k}</td>'
        f'<td style="font-weight:600;font-size:12px">{v}</td></tr>'
        for k, v in lines
    )
    return (
        f'<div style="font-family:Inter,sans-serif;min-width:150px">'
        f'<table style="border-collapse:collapse">{rows}</table></div>'
    )


def _base_map(zoom: int = 2) -> folium.Map:
    return folium.Map(
        location=[20, 0],
        zoom_start=zoom,
        tiles=MAP_TILES,
        attr="CartoDB",
    )


def _empty_state(icon: str, msg: str):
    st.markdown(
        f'<div class="empty-state"><div class="icon">{icon}</div>'
        f'<div class="msg">{msg}</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_track, tab_hubble, tab_coverage, tab_passes = st.tabs(
    ["📡  Track Group", "🌐  Hubble Network", "🗺️  Coverage Analysis", "🔭  Pass Predictions"]
)

# ── Tab 1: Track a satellite group ────────────────────────────────────────
with tab_track:
    col_ctrl, col_map = st.columns([1, 3.5], gap="large")

    with col_ctrl:
        st.markdown('<p class="control-label">Satellite Group</p>', unsafe_allow_html=True)
        group = st.selectbox(
            "Satellite Group",
            SATELLITE_GROUPS,
            index=0,
            label_visibility="collapsed",
        )
        st.markdown('<p class="control-label">Max Satellites</p>', unsafe_allow_html=True)
        limit = st.slider("Max satellites", 5, 50, 15, label_visibility="collapsed")
        st.button("🔄  Refresh", key="track_refresh", use_container_width=True)

    with col_map:
        with st.spinner(f"Fetching {group} satellites…"):
            satellites = fetch_by_group(group)
            positions = []
            for sat in satellites[:limit]:
                pos = calculate_position(sat)
                if pos:
                    positions.append(pos)

        if positions:
            m = _base_map()
            for pos in positions:
                popup_html = _make_popup_html([
                    ("Satellite", pos.name),
                    ("NORAD", str(pos.norad_id)),
                    ("Altitude", f"{pos.altitude_km:,.0f} km"),
                    ("Velocity", f"{pos.velocity_km_s:.1f} km/s"),
                ])
                folium.CircleMarker(
                    location=[pos.latitude, pos.longitude],
                    radius=5,
                    color="#818cf8",
                    fill=True,
                    fill_color="#818cf8",
                    fill_opacity=0.85,
                    popup=folium.Popup(popup_html, max_width=220),
                    tooltip=pos.name,
                ).add_to(m)
            st_folium(m, width=None, height=480, returned_objects=[])

            st.markdown(
                f'<p class="section-heading">{group.upper()} &mdash; '
                f'{len(positions)} satellites</p>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                [
                    {
                        "Satellite": p.name,
                        "NORAD ID": p.norad_id,
                        "Lat": round(p.latitude, 2),
                        "Lon": round(p.longitude, 2),
                        "Alt (km)": f"{p.altitude_km:,.0f}",
                        "Vel (km/s)": f"{p.velocity_km_s:.2f}",
                    }
                    for p in positions
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            _empty_state("📡", "No satellite positions available for this group.")

# ── Tab 2: Hubble Network ─────────────────────────────────────────────────
with tab_hubble:
    with st.spinner("Fetching Hubble Network satellites…"):
        hubble_sats = _fetch_hubble_sats()
        hubble_positions = []
        for sat in hubble_sats:
            pos = calculate_position(sat)
            if pos:
                hubble_positions.append(pos)

    if hubble_positions:
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Satellites", str(len(hubble_positions)))
        avg_alt = sum(p.altitude_km for p in hubble_positions) / len(hubble_positions)
        mc2.metric("Avg Altitude", f"{avg_alt:,.0f} km")
        avg_vel = sum(p.velocity_km_s for p in hubble_positions) / len(hubble_positions)
        mc3.metric("Avg Velocity", f"{avg_vel:.2f} km/s")

        st.markdown("", unsafe_allow_html=True)

        hm = _base_map()
        for pos in hubble_positions:
            popup_html = _make_popup_html([
                ("Satellite", pos.name),
                ("NORAD", str(pos.norad_id)),
                ("Altitude", f"{pos.altitude_km:,.0f} km"),
                ("Velocity", f"{pos.velocity_km_s:.1f} km/s"),
            ])
            folium.CircleMarker(
                location=[pos.latitude, pos.longitude],
                radius=8,
                color="#f472b6",
                fill=True,
                fill_color="#f472b6",
                fill_opacity=0.9,
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=pos.name,
            ).add_to(hm)

        for city_name, (lat, lon) in CITIES.items():
            if city_name in ("tel aviv", "seattle"):
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.Icon(color="cadetblue", icon="home", prefix="fa"),
                    tooltip=city_name.title(),
                ).add_to(hm)

        st_folium(hm, width=None, height=480, returned_objects=[])

        st.markdown(
            '<p class="section-heading">Constellation Details</p>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            [
                {
                    "Satellite": p.name,
                    "NORAD ID": p.norad_id,
                    "Lat": round(p.latitude, 2),
                    "Lon": round(p.longitude, 2),
                    "Alt (km)": f"{p.altitude_km:,.0f}",
                    "Vel (km/s)": f"{p.velocity_km_s:.2f}",
                }
                for p in hubble_positions
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        _empty_state("🌐", "Could not load Hubble Network satellites.")

# ── Tab 3: Coverage Analysis ──────────────────────────────────────────────
with tab_coverage:
    st.markdown(
        '<p class="section-description">'
        "Analyze how Hubble Network's constellation covers the globe — "
        "ground tracks, coverage density, and per-city pass analysis.</p>",
        unsafe_allow_html=True,
    )

    col_cfg, col_main = st.columns([1, 3.5], gap="large")

    with col_cfg:
        st.markdown('<p class="control-label">Analysis Window</p>', unsafe_allow_html=True)
        cov_hours = st.select_slider(
            "Analysis window",
            options=[6, 12, 24, 48],
            value=24,
            format_func=lambda x: f"{x}h",
            label_visibility="collapsed",
        )
        st.markdown('<p class="control-label">Min Elevation (°)</p>', unsafe_allow_html=True)
        cov_min_el = st.slider(
            "Min elevation (°)", 5, 30, 10, label_visibility="collapsed"
        )
        analyze = st.button("🚀  Run Analysis", type="primary", use_container_width=True)

    if analyze:
        with st.spinner("Fetching Hubble Network constellation…"):
            h_sats = _fetch_hubble_sats()

        if not h_sats:
            st.error("Could not find Hubble Network satellites.")
        else:
            with st.spinner(
                f"Propagating {len(h_sats)} satellites over {cov_hours} hours…"
            ):
                tracks = compute_ground_tracks(h_sats, hours=cov_hours, step_seconds=60)

            with col_main:
                cm = _base_map()

                track_layer = FeatureGroup(name="Ground Tracks", show=True)
                heat_layer = FeatureGroup(name="Coverage Heatmap", show=True)

                heat_data = []
                for idx, (sat_name, points) in enumerate(tracks.items()):
                    color = SAT_COLORS[idx % len(SAT_COLORS)]

                    segments: list[list[list[float]]] = [[]]
                    for j, pt in enumerate(points):
                        if j > 0 and abs(pt.longitude - points[j - 1].longitude) > 180:
                            segments.append([])
                        segments[-1].append([pt.latitude, pt.longitude])

                    for seg in segments:
                        if len(seg) > 1:
                            folium.PolyLine(
                                seg,
                                color=color,
                                weight=2,
                                opacity=0.55,
                                tooltip=sat_name,
                            ).add_to(track_layer)

                    heat_data.extend(
                        [[pt.latitude, pt.longitude, 1] for pt in points]
                    )

                HeatMap(
                    heat_data,
                    radius=20,
                    blur=15,
                    max_zoom=6,
                    gradient={
                        0.2: "#312e81",
                        0.4: "#6366f1",
                        0.6: "#34d399",
                        0.8: "#fbbf24",
                        1.0: "#ef4444",
                    },
                ).add_to(heat_layer)

                track_layer.add_to(cm)
                heat_layer.add_to(cm)

                for city_name, (lat, lon) in CITIES.items():
                    folium.Marker(
                        location=[lat, lon],
                        icon=folium.Icon(color="cadetblue", icon="info-sign"),
                        tooltip=city_name.title(),
                    ).add_to(cm)

                folium.LayerControl(collapsed=False).add_to(cm)
                st_folium(cm, width=None, height=500, returned_objects=[])

            st.markdown("---")
            st.markdown(
                '<p class="section-heading">Per-City Coverage</p>',
                unsafe_allow_html=True,
            )

            target_cities = [
                ("tel aviv", *CITIES["tel aviv"]),
                ("seattle", *CITIES["seattle"]),
            ]

            city_cols = st.columns(len(target_cities), gap="large")

            for i, (cname, clat, clon) in enumerate(target_cities):
                with city_cols[i]:
                    with st.spinner(f"Analyzing {cname.title()}…"):
                        report = compute_city_coverage(
                            h_sats,
                            cname,
                            clat,
                            clon,
                            hours=cov_hours,
                            min_elevation_deg=cov_min_el,
                        )

                    st.markdown(
                        f'<p class="section-heading" style="text-align:center">'
                        f'{cname.title()}</p>',
                        unsafe_allow_html=True,
                    )
                    m1, m2 = st.columns(2)
                    m1.metric("Coverage", f"{report.coverage_percentage}%")
                    m2.metric("Passes", str(report.num_passes))
                    m3, m4 = st.columns(2)
                    m3.metric("Max Gap", f"{report.max_gap_minutes:.0f} min")
                    m4.metric(
                        "Avg Pass",
                        f"{report.avg_pass_duration_seconds:.0f}s",
                    )

                    if report.windows:
                        st.dataframe(
                            [
                                {
                                    "Satellite": w.satellite_name,
                                    "Start": w.start_time.strftime("%H:%M"),
                                    "End": w.end_time.strftime("%H:%M"),
                                    "Dur": f"{int(w.duration_seconds)}s",
                                    "Max El": f"{w.max_elevation_deg}°",
                                }
                                for w in report.windows
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        _empty_state("📡", "No passes in this window.")
    else:
        with col_main:
            _empty_state(
                "🗺️",
                "Configure parameters and press Run Analysis to begin.",
            )

# ── Tab 4: Pass Predictions ───────────────────────────────────────────────
with tab_passes:
    col_ctrl, col_results = st.columns([1, 3.5], gap="large")

    with col_ctrl:
        st.markdown('<p class="control-label">City</p>', unsafe_allow_html=True)
        city = st.selectbox(
            "City",
            list(CITIES.keys()),
            format_func=str.title,
            label_visibility="collapsed",
        )
        st.markdown('<p class="control-label">Satellite Name</p>', unsafe_allow_html=True)
        sat_name = st.text_input(
            "Satellite name", value="ISS", label_visibility="collapsed"
        )
        st.markdown('<p class="control-label">Min Elevation (°)</p>', unsafe_allow_html=True)
        min_el = st.slider(
            "Min elevation (°)", 0, 45, 10, label_visibility="collapsed"
        )
        predict = st.button(
            "🔭  Predict Passes", key="predict", use_container_width=True
        )

    with col_results:
        if predict or sat_name:
            lat, lon = CITIES[city]
            with st.spinner(f"Searching for {sat_name} and calculating passes…"):
                from sattracker.calculator import predict_passes

                sats = fetch_by_name(sat_name)
                if not sats:
                    _empty_state("🔍", f"No satellite found matching '{sat_name}'")
                else:
                    all_passes = []
                    for sat in sats[:3]:
                        passes = predict_passes(sat, lat, lon, min_elevation=min_el)
                        all_passes.extend(passes)
                    all_passes.sort(key=lambda p: p.rise_time)

                    if all_passes:
                        st.markdown(
                            f'<p class="section-heading">'
                            f'Passes over {city.title()} &mdash; next 24 h</p>',
                            unsafe_allow_html=True,
                        )
                        st.dataframe(
                            [
                                {
                                    "Satellite": p.satellite_name,
                                    "Rise (UTC)": p.rise_time.strftime("%H:%M:%S"),
                                    "Set (UTC)": p.set_time.strftime("%H:%M:%S"),
                                    "Duration": (
                                        f"{int(p.duration_seconds // 60)}m "
                                        f"{int(p.duration_seconds % 60)}s"
                                    ),
                                    "Max El": f"{p.max_elevation_deg}°",
                                    "Peak (UTC)": p.max_elevation_time.strftime(
                                        "%H:%M:%S"
                                    ),
                                }
                                for p in all_passes
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        _empty_state(
                            "🔭",
                            f"No passes above {min_el}° in the next 24 hours.",
                        )
        else:
            _empty_state("🔭", "Enter a satellite name and press Predict Passes.")
