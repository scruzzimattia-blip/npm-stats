"""Map components for NPM Monitor."""

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster


def render_geo_map(df: pd.DataFrame) -> None:
    """Render a robust Folium map with marker clusters."""
    if df.empty or "latitude" not in df.columns or "longitude" not in df.columns:
        st.info("Keine Geodaten für die Kartenanzeige verfügbar.")
        return

    # Filter and group
    map_df = df.dropna(subset=["latitude", "longitude"]).copy()
    
    if map_df.empty:
        st.info("Keine gültigen Koordinaten in den aktuellen Daten gefunden.")
        return

    st.subheader("🌐 Globale Traffic-Verteilung")
    
    # Create base map
    m = folium.Map(
        location=[20, 0], 
        zoom_start=2,
        tiles="CartoDB dark_matter" # Clean dark theme
    )
    
    marker_cluster = MarkerCluster().add_to(m)
    
    # Aggregate for performance if many points
    agg_df = map_df.groupby(["latitude", "longitude", "city", "country_code"]).size().reset_index(name="count")
    
    for _, row in agg_df.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=min(15, 5 + (row["count"] / 100)),
            popup=f"<b>{row['city']}, {row['country_code']}</b><br>Requests: {row['count']}",
            color="#ff4b4b",
            fill=True,
            fill_color="#ff4b4b",
            fill_opacity=0.7,
        ).add_to(marker_cluster)

    # Render map
    st_folium(m, width="100%", height=500, returned_objects=[])
