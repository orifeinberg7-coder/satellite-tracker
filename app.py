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

st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; }
    h1 { font-size: 2rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🛰️ Satellite Tracker")
st.caption("Real-time satellite tracking powered by CelesTrak + SGP4")

SAT_COLORS = ["#ff6b35", "#ffd700", "#00d4ff", "#ff1493", "#00ff7f", "#ff4500", "#9370db"]

tab_track, tab_hubble, tab_coverage, tab_passes = st.tabs(
    ["Track Group", "Hubble Network", "Coverage Analysis", "Pass Predictions"]
)


def _fetch_hubble_sats():
    """Fetch Hubble Network satellites, falling back to name search."""
    all_hubble = fetch_by_name("HUBBLE")
    hubble_sats = [s for s in all_hubble if s.norad_id in HUBBLE_NETWORK_IDS]
    if not hubble_sats:
        hubble_sats = [s for s in all_hubble if s.norad_id != 20580]
    return hubble_sats


# --- Tab 1: Track a satellite group ---
with tab_track:
    col1, col2 = st.columns([1, 3])
    with col1:
        group = st.selectbox("Satellite Group", SATELLITE_GROUPS, index=0)
        limit = st.slider("Max satellites", 5, 50, 15)
        st.button("Refresh", key="track_refresh")

    with col2:
        with st.spinner(f"Fetching {group} satellites..."):
            satellites = fetch_by_group(group)
            positions = []
            for sat in satellites[:limit]:
                pos = calculate_position(sat)
                if pos:
                    positions.append(pos)

        if positions:
            m = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
            for pos in positions:
                folium.CircleMarker(
                    location=[pos.latitude, pos.longitude],
                    radius=5,
                    color="#00d4ff",
                    fill=True,
                    fill_opacity=0.9,
                    popup=folium.Popup(
                        f"<b>{pos.name}</b><br>"
                        f"Alt: {pos.altitude_km:,.0f} km<br>"
                        f"Vel: {pos.velocity_km_s:.1f} km/s",
                        max_width=200,
                    ),
                    tooltip=pos.name,
                ).add_to(m)
            st_folium(m, width=None, height=500, returned_objects=[])

            st.dataframe(
                [
                    {
                        "Satellite": p.name,
                        "NORAD ID": p.norad_id,
                        "Latitude": p.latitude,
                        "Longitude": p.longitude,
                        "Altitude (km)": p.altitude_km,
                        "Velocity (km/s)": p.velocity_km_s,
                    }
                    for p in positions
                ],
                use_container_width=True,
                hide_index=True,
            )

# --- Tab 2: Hubble Network ---
with tab_hubble:
    with st.spinner("Fetching Hubble Network satellites..."):
        hubble_sats = _fetch_hubble_sats()
        hubble_positions = []
        for sat in hubble_sats:
            pos = calculate_position(sat)
            if pos:
                hubble_positions.append(pos)

    if hubble_positions:
        st.subheader(f"🌐 {len(hubble_positions)} Hubble Network Satellites in Orbit")

        hm = folium.Map(location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter")
        for pos in hubble_positions:
            folium.CircleMarker(
                location=[pos.latitude, pos.longitude],
                radius=8,
                color="#ff6b35",
                fill=True,
                fill_color="#ff6b35",
                fill_opacity=0.9,
                popup=folium.Popup(
                    f"<b>{pos.name}</b><br>"
                    f"NORAD: {pos.norad_id}<br>"
                    f"Alt: {pos.altitude_km:,.0f} km<br>"
                    f"Vel: {pos.velocity_km_s:.1f} km/s",
                    max_width=200,
                ),
                tooltip=pos.name,
            ).add_to(hm)

        for city_name, (lat, lon) in CITIES.items():
            if city_name in ("tel aviv", "seattle"):
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.Icon(color="green", icon="home"),
                    tooltip=city_name.title(),
                ).add_to(hm)

        st_folium(hm, width=None, height=500, returned_objects=[])

        st.dataframe(
            [
                {
                    "Satellite": p.name,
                    "NORAD ID": p.norad_id,
                    "Latitude": p.latitude,
                    "Longitude": p.longitude,
                    "Altitude (km)": p.altitude_km,
                    "Velocity (km/s)": p.velocity_km_s,
                }
                for p in hubble_positions
            ],
            use_container_width=True,
            hide_index=True,
        )

# --- Tab 3: Coverage Analysis ---
with tab_coverage:
    st.markdown(
        "Analyze how Hubble Network's constellation covers the globe — "
        "ground tracks, coverage density, and per-city pass analysis."
    )

    col_cfg, col_main = st.columns([1, 3])

    with col_cfg:
        cov_hours = st.select_slider(
            "Analysis window",
            options=[6, 12, 24, 48],
            value=24,
            format_func=lambda x: f"{x}h",
        )
        cov_min_el = st.slider("Min elevation (°)", 5, 30, 10)
        analyze = st.button("Run Analysis", type="primary")

    if analyze:
        with st.spinner("Fetching Hubble Network constellation..."):
            h_sats = _fetch_hubble_sats()

        if not h_sats:
            st.error("Could not find Hubble Network satellites.")
        else:
            with st.spinner(
                f"Propagating {len(h_sats)} satellites over {cov_hours} hours..."
            ):
                tracks = compute_ground_tracks(h_sats, hours=cov_hours, step_seconds=60)

            with col_main:
                cm = folium.Map(
                    location=[20, 0], zoom_start=2, tiles="CartoDB dark_matter"
                )

                track_layer = FeatureGroup(name="Ground Tracks")
                heat_layer = FeatureGroup(name="Coverage Heatmap")

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
                                opacity=0.6,
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
                        0.2: "#0d47a1",
                        0.4: "#00bcd4",
                        0.6: "#4caf50",
                        0.8: "#ffeb3b",
                        1.0: "#f44336",
                    },
                ).add_to(heat_layer)

                track_layer.add_to(cm)
                heat_layer.add_to(cm)

                for city_name, (lat, lon) in CITIES.items():
                    folium.Marker(
                        location=[lat, lon],
                        icon=folium.Icon(color="green", icon="info-sign"),
                        tooltip=city_name.title(),
                    ).add_to(cm)

                folium.LayerControl().add_to(cm)
                st_folium(cm, width=None, height=520, returned_objects=[])

            st.markdown("---")
            st.subheader("Per-City Coverage")

            target_cities = [
                ("tel aviv", *CITIES["tel aviv"]),
                ("seattle", *CITIES["seattle"]),
            ]

            city_cols = st.columns(len(target_cities))

            for i, (cname, clat, clon) in enumerate(target_cities):
                with city_cols[i]:
                    with st.spinner(f"Analyzing {cname.title()}..."):
                        report = compute_city_coverage(
                            h_sats,
                            cname,
                            clat,
                            clon,
                            hours=cov_hours,
                            min_elevation_deg=cov_min_el,
                        )

                    st.markdown(f"### {cname.title()}")
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
                                    "Start (UTC)": w.start_time.strftime("%H:%M"),
                                    "End (UTC)": w.end_time.strftime("%H:%M"),
                                    "Duration": f"{int(w.duration_seconds)}s",
                                    "Max El": f"{w.max_elevation_deg}°",
                                }
                                for w in report.windows
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info("No passes in this window.")

# --- Tab 4: Pass Predictions ---
with tab_passes:
    col1, col2 = st.columns([1, 3])
    with col1:
        city = st.selectbox("City", list(CITIES.keys()), format_func=str.title)
        sat_name = st.text_input("Satellite name", value="ISS")
        min_el = st.slider("Min elevation (°)", 0, 45, 10)
        predict = st.button("Predict Passes", key="predict")

    with col2:
        if predict or sat_name:
            lat, lon = CITIES[city]
            with st.spinner(f"Searching for {sat_name} and calculating passes..."):
                from sattracker.calculator import predict_passes

                sats = fetch_by_name(sat_name)
                if not sats:
                    st.warning(f"No satellite found matching '{sat_name}'")
                else:
                    all_passes = []
                    for sat in sats[:3]:
                        passes = predict_passes(sat, lat, lon, min_elevation=min_el)
                        all_passes.extend(passes)
                    all_passes.sort(key=lambda p: p.rise_time)

                    if all_passes:
                        st.subheader(f"Passes over {city.title()} (next 24h)")
                        st.dataframe(
                            [
                                {
                                    "Satellite": p.satellite_name,
                                    "Rise (UTC)": p.rise_time.strftime("%H:%M:%S"),
                                    "Set (UTC)": p.set_time.strftime("%H:%M:%S"),
                                    "Duration": f"{int(p.duration_seconds // 60)}m {int(p.duration_seconds % 60)}s",
                                    "Max Elevation": f"{p.max_elevation_deg}°",
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
                        st.info(
                            f"No passes above {min_el}° in the next 24 hours."
                        )
