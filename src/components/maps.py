"""Map components for NPM Monitor."""

import os

import pandas as pd
import pydeck as pdk
import streamlit as st

# Default server coordinates (can be overridden by environment)
SERVER_LAT = float(os.getenv("SERVER_LAT", "51.1657"))
SERVER_LON = float(os.getenv("SERVER_LON", "10.4515"))

def render_geo_map(df: pd.DataFrame) -> None:
    """Render an advanced 3D Threat Map using pydeck."""
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        st.info("Keine Geodaten für die Kartenanzeige verfügbar.")
        return

    # Filter and group
    map_df = df.dropna(subset=["latitude", "longitude"]).copy()

    if map_df.empty:
        st.info("Keine gültigen Koordinaten in den aktuellen Daten gefunden.")
        return

    st.subheader("🗺️ Live Threat Map (3D)")

    # 1. Aggregate points for base visualization
    agg_df = map_df.groupby(["latitude", "longitude", "city", "country_code"]).size().reset_index(name="count")

    # 2. Create Arc Data (From Attacker to Server)
    agg_df["server_lat"] = SERVER_LAT
    agg_df["server_lon"] = SERVER_LON

    # Define layers
    # Hexagon/Heatmap for volume
    point_layer = pdk.Layer(
        "ScatterplotLayer",
        agg_df,
        get_position=["longitude", "latitude"],
        get_color="[255, 75, 75, 160]",
        get_radius="count * 500",
        radius_min_pixels=5,
        radius_max_pixels=50,
        pickable=True,
    )

    # Arc Layer for the "Laser Beam" effect
    arc_layer = pdk.Layer(
        "ArcLayer",
        agg_df,
        get_source_position=["longitude", "latitude"],
        get_target_position=["server_lon", "server_lat"],
        get_source_color="[255, 75, 75, 200]",
        get_target_color="[0, 212, 255, 200]",
        get_width="1 + (count / 10)",
        pickable=True,
    )

    # Target point (Your Server)
    server_layer = pdk.Layer(
        "ScatterplotLayer",
        pd.DataFrame([{"lat": SERVER_LAT, "lon": SERVER_LON}]),
        get_position=["lon", "lat"],
        get_color="[0, 212, 255, 255]",
        get_radius=50000,
        radius_min_pixels=10,
        pickable=True,
    )

    # Set viewport
    view_state = pdk.ViewState(
        latitude=20,
        longitude=0,
        zoom=1.5,
        pitch=45,
        bearing=0
    )

    # Render deck
    r = pdk.Deck(
        layers=[point_layer, arc_layer, server_layer],
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/dark-v10",
        tooltip={
            "html": "<b>Ort:</b> {city}, {country_code}<br/><b>Anfragen:</b> {count}",
            "style": {"color": "white"}
        }
    )

    st.pydeck_chart(r)

    # Small legend
    st.caption(f"🔵 Dein Standort ({SERVER_LAT}, {SERVER_LON}) | 🔴 Angreifer-Quellen")
