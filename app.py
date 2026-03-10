import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static
from folium.plugins import HeatMap
import requests
import gpxpy
from io import BytesIO
import os
import math
from streamlit_geolocation import streamlit_geolocation
import simplekml
import qrcode

st.set_page_config(page_title="ND Hunt & Fish Navigator", layout="wide")
st.title("🐦🎣 ND Hunt & Fish Navigator")
st.caption("onX AI Predictive Hunting System • Team Mode • Multi-species • AI alerts • Full route GPX + KML + QR sharing")

# ========================= PERSISTENCE =========================
CSV_FILE = "season_log.csv"
PHOTO_DIR = "photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
else:
    df = pd.DataFrame(columns=["Date", "User", "Mode", "Location", "Birds Flushed", "Shots Fired",
                               "Harvest/Catch", "Wind Speed", "Notes", "Photo_Path",
                               "Miles Walked", "Species", "Dog Points", "Dog Retrieves"])

if "logs" not in st.session_state:
    st.session_state.logs = df.copy()

# ========================= HAVERSINE =========================
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ========================= WEATHER =========================
lat = round(st.session_state.get("auto_lat", 48.15), 2)
lon = round(st.session_state.get("auto_lon", -103.62), 2)

@st.cache_data(ttl=900)
def get_weather(latitude, longitude):
    try:
        w = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=wind_speed_10m,wind_direction_10m&daily=sunrise,sunset&timezone=auto").json()
        return {"wind_speed": w["current"]["wind_speed_10m"], "wind_dir": w["current"]["wind_direction_10m"], "sunrise": w["daily"]["sunrise"][0].split("T")[1], "sunset": w["daily"]["sunset"][0].split("T")[1]}
    except:
        st.warning("Weather API unavailable — demo data")
        return {"wind_speed": 12, "wind_dir": 180, "sunrise": "06:30", "sunset": "19:45"}

weather = get_weather(lat, lon)
wind_speed = weather["wind_speed"]
wind_dir = weather["wind_dir"]

# ========================= SIDEBAR =========================
with st.sidebar:
    st.header("User & Activity")
    user_name = st.text_input("Your name", value="Hunter1")
    mode = st.radio("Activity", ["Hunting", "Fishing"])
    if mode == "Hunting":
        species = st.selectbox("Target Species", ["Pheasant", "Duck", "Deer"], index=0)
        dog_points = st.number_input("Dog Points", min_value=0, value=0)
        dog_retrieves = st.number_input("Dog Retrieves", min_value=0, value=0)
    else:
        species = st.selectbox("Target Species", ["Walleye", "Bass", "Northern Pike"], index=0)
        dog_points = dog_retrieves = None

    st.header("AI Settings")
    cluster_radius = st.slider("Cluster Radius (yards)", 50, 300, 150)
    decay_rate = st.slider("Temporal Decay (days)", 10, 90, 30)
    weeks_filter = st.slider("Show last X weeks", 1, 52, 12)

    st.header("GPX Import")
    uploaded_gpx = st.file_uploader("Import GPX", type=["gpx"])
    if uploaded_gpx:
        gpx = gpxpy.parse(uploaded_gpx)
        points = [(p.latitude, p.longitude) for track in gpx.tracks for seg in track.segments for p in seg.points]
        waypoints = []
        for wp in gpx.waypoints:
            name = wp.name or "Waypoint"
            wp_date = wp.time.strftime("%Y-%m-%d") if hasattr(wp, 'time') and wp.time else datetime.now().strftime("%Y-%m-%d")
            waypoints.append((wp.latitude, wp.longitude, name, wp_date))
        st.session_state.current_route = points
        st.session_state.waypoints = waypoints
        st.success("✅ GPX loaded!")

    st.header("Quick GPS")
    geo = streamlit_geolocation()
    if geo and st.button("📍 Use Current GPS"):
        st.session_state.auto_lat = geo["latitude"]
        st.session_state.auto_lon = geo["longitude"]
        st.success(f"📍 GPS locked: {geo['latitude']:.4f}, {geo['longitude']:.4f}")

    st.header("Log Activity")
    location = st.text_input("Location", value=f"{st.session_state.get('auto_lat',48.15):.4f}, {st.session_state.get('auto_lon',-103.62):.4f}")
    if mode == "Hunting":
        flushed = st.number_input("Birds Flushed", min_value=0, value=0)
        shots = st.number_input("Shots Fired", min_value=0, value=0)
        harvest = st.number_input("Birds Harvested", min_value=0, value=0)
    else:
        flushed = shots = None
        harvest = st.text_input("Species & Length")
    miles = st.number_input("Miles Walked", min_value=0.0, value=0.0)
    notes = st.text_area("Notes")
    photo = st.file_uploader("Upload Photo", type=["jpg","png","jpeg"])

    if st.button("Log Activity"):
        photo_path = ""
        if photo:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            photo_path = os.path.join(PHOTO_DIR, f"{ts}_{photo.name}")
            with open(photo_path,"wb") as f: f.write(photo.getbuffer())
        new_log = pd.DataFrame({
            "Date":[datetime.now().strftime("%Y-%m-%d")],
            "User":[user_name], "Mode":[mode], "Location":[location],
            "Birds Flushed":[flushed], "Shots Fired":[shots],
            "Harvest/Catch":[harvest], "Wind Speed":[wind_speed],
            "Notes":[notes], "Photo_Path":[photo_path], "Miles Walked":[miles],
            "Species":[species], "Dog Points":[dog_points], "Dog Retrieves":[dog_retrieves]
        })
        st.session_state.logs = pd.concat([st.session_state.logs,new_log], ignore_index=True)
        st.session_state.logs.to_csv(CSV_FILE,index=False)
        st.success(f"✅ {user_name} logged {mode} at {location}!")

# ========================= TABS =========================
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Map","📊 Tracker","📤 PDF","🧠 AI Map"])

with tab4:
    st.subheader("🧠 AI Probability Map + Satellite Habitat")
    if st.button("🚀 Load Demo Data (test without GPX)"):
        st.session_state.waypoints = [
            (48.15, -103.62, "Flush", "2026-03-01"),
            (48.16, -103.61, "Bird", "2026-03-02"),
            (48.14, -103.63, "Rooster", "2026-03-03"),
            (48.15, -103.60, "Walleye", "2026-03-04")
        ]
        st.session_state.current_route = [(48.15, -103.62), (48.16, -103.61), (48.14, -103.63)]
        st.success("✅ Demo data loaded! Scroll down to see the full AI map.")

    flush_points = []

    if "waypoints" in st.session_state and "current_route" in st.session_state:
        route_points = st.session_state.current_route
        if route_points:
            center_lat = sum(p[0] for p in route_points)/len(route_points)
            center_lon = sum(p[1] for p in route_points)/len(route_points)
        elif st.session_state.waypoints:
            center_lat = sum(w[0] for w in st.session_state.waypoints)/len(st.session_state.waypoints)
            center_lon = sum(w[1] for w in st.session_state.waypoints)/len(st.session_state.waypoints)
        else:
            center_lat, center_lon = lat, lon
