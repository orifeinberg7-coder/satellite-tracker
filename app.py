"""Streamlit web dashboard for satellite tracking."""

import streamlit as st
import folium
from streamlit_folium import st_folium

from sattracker.fetcher import fetch_by_group, fetch_by_name, SATELLITE_GROUPS
from sattracker.calculator import calculate_position, predict_passes, CITIES
from sattracker.cli import HUBBLE_NETWORK_IDS

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

tab_track, tab_hubble, tab_passes = st.tabs(["Track Group", "Hubble Network", "Pass Predictions"])

# --- Tab 1: Track a satellite group ---
with tab_track:
    col1, col2 = st.columns([1, 3])
    with col1:
        group = st.selectbox("Satellite Group", SATELLITE_GROUPS, index=0)
        limit = st.slider("Max satellites", 5, 50, 15)
        refresh = st.button("Refresh", key="track_refresh")

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
        all_hubble = fetch_by_name("HUBBLE")
        hubble_sats = [s for s in all_hubble if s.norad_id in HUBBLE_NETWORK_IDS]
        if not hubble_sats:
            hubble_sats = [s for s in all_hubble if s.norad_id != 20580]

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

        # Mark cities
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

# --- Tab 3: Pass Predictions ---
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
                                    "Peak (UTC)": p.max_elevation_time.strftime("%H:%M:%S"),
                                }
                                for p in all_passes
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info(f"No passes above {min_el}° in the next 24 hours.")
