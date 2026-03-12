"""Map components for NPM Monitor."""

import pandas as pd
import streamlit as st
import pydeck as pdk


def render_geo_map(df: pd.DataFrame) -> None:
    """Render an elegant Heatmap and Scatter map of traffic sources."""
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        st.info("Keine Geodaten für die Kartenanzeige verfügbar.")
        return

    # Filter out rows without coordinates and group by location
    map_df = df.dropna(subset=["latitude", "longitude"]).copy()
    
    if map_df.empty:
        st.info("Keine gültigen Koordinaten in den aktuellen Daten gefunden.")
        return

    st.subheader("🌐 Globale Traffic-Verteilung")
    
    # Aggregate data for points
    agg_df = map_df.groupby(["latitude", "longitude", "city", "country_code"]).size().reset_index(name="count")
    
    # Heatmap Layer for overall intensity
    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        map_df,
        get_position=["longitude", "latitude"],
        aggregation=pdk.types.String("SUM"),
        get_weight="1",
        radius_pixels=30,
        intensity=1,
        threshold=0.05,
        opacity=0.6,
    )

    # Scatterplot Layer for individual locations
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        agg_df,
        get_position=["longitude", "latitude"],
        get_color="[255, 75, 75, 180]", # Streamlit Red
        get_radius="10000 + (count * 500)", # Dynamic radius based on request count
        radius_min_pixels=3,
        radius_max_pixels=15,
        pickable=True,
    )

    # Set the viewport - zoom out a bit for better overview
    view_state = pdk.ViewState(
        latitude=20, # Center more globally
        longitude=0,
        zoom=1.2,
        pitch=0, # Flat map often looks cleaner for overview
    )

    # Render map with dark style
    st.pydeck_chart(
        pdk.Deck(
            layers=[heatmap_layer, scatter_layer],
            initial_view_state=view_state,
            map_style="mapbox://styles/mapbox/dark-v11", # Professional dark theme
            tooltip={
                "html": "<b>Ort:</b> {city}, {country_code}<br/><b>Requests:</b> {count}",
                "style": {"color": "white", "backgroundColor": "#262730", "fontSize": "12px"},
            },
        )
    )
