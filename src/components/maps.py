"""Map components for NPM Monitor."""

import pandas as pd
import streamlit as st
import pydeck as pdk


def render_geo_map(df: pd.DataFrame) -> None:
    """Render an interactive 3D map of traffic sources."""
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        st.info("Keine Geodaten für die Kartenanzeige verfügbar.")
        return

    # Filter out rows without coordinates
    map_df = df.dropna(subset=["latitude", "longitude"]).copy()
    
    if map_df.empty:
        st.info("Keine gültigen Koordinaten in den aktuellen Daten gefunden.")
        return

    st.subheader("🌐 Globale Traffic-Quellen")
    
    # Aggregate data by coordinates for better visualization
    agg_df = map_df.groupby(["latitude", "longitude", "city", "country_code"]).size().reset_index(name="count")
    
    # Layer for the hexbins
    layer = pdk.Layer(
        "HexagonLayer",
        map_df,
        get_position=["longitude", "latitude"],
        auto_highlight=True,
        elevation_scale=50,
        pickable=True,
        elevation_range=[0, 3000],
        extruded=True,
        coverage=1,
    )

    # Layer for scatter points
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        agg_df,
        get_position=["longitude", "latitude"],
        get_color="[200, 30, 0, 160]",
        get_radius="count * 100",
        pickable=True,
    )

    # Set the viewport
    view_state = pdk.ViewState(
        latitude=map_df["latitude"].mean(),
        longitude=map_df["longitude"].mean(),
        zoom=1,
        pitch=45,
    )

    # Render map
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer, scatter_layer],
            initial_view_state=view_state,
            tooltip={
                "html": "<b>Ort:</b> {city}, {country_code}<br/><b>Requests:</b> {count}",
                "style": {"color": "white"},
            },
        )
    )
