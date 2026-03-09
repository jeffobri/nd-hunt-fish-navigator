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
        return {"wind_speed": w["current"]["wind_speed_10m"],
                "wind_dir": w["current"]["wind_direction_10m"],
                "sunrise": w["daily"]["sunrise"][0].split("T")[1],
                "sunset": w["daily"]["sunset"][0].split("T")[1]}
    except:
        st.warning("Weather API unavailable — demo data")
        return {"wind_speed": 12, "wind_dir": 180, "sunrise": "06:30", "sunset": "19:45"}

weather = get_weather(lat, lon)
wind_speed = weather["wind_speed"]
wind_dir = weather["wind_dir"]
sunrise = weather["sunrise"]
sunset = weather["sunset"]

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
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Map", "📊 Tracker", "📤 PDF", "🧠 AI Map"])

with tab4:
    st.subheader("🧠 AI Probability Map + Satellite Habitat")
    flush_points = []

    if "waypoints" in st.session_state and "current_route" in st.session_state:
        route_points = st.session_state.current_route
        center_lat = sum(p[0] for p in route_points)/len(route_points) if route_points else lat
        center_lon = sum(p[1] for p in route_points)/len(route_points) if route_points else lon

        today = datetime.now().date()
        radius_miles = cluster_radius / 1760.0

        keywords = ["flush", "bird", "rooster", "buck", "deer", "duck"] if mode == "Hunting" else ["bite", "fish", "walleye", "catch", "spot"]

        for lat_w, lon_w, name, date_w in st.session_state.waypoints:
            days_old = (today - datetime.strptime(date_w,"%Y-%m-%d").date()).days
            if days_old > (weeks_filter * 7): continue
            if any(k in (name or "").lower() for k in keywords):
                decay = math.exp(-days_old / decay_rate)
                hist_row = st.session_state.logs[st.session_state.logs["Date"]==date_w]
                wind_sim = 1.0 if not hist_row.empty and abs(wind_speed-hist_row["Wind Speed"].iloc[0])<=5 else 0.3
                cluster_weight = 1.0
                for ex in flush_points:
                    if haversine_distance(lat_w, lon_w, ex[0], ex[1]) < radius_miles:
                        cluster_weight += 0.6
                habitat_weight = 1.3
                final_w = decay * wind_sim * cluster_weight * habitat_weight

                offset_dist = 0.12
                downwind_dir = (wind_dir + 180) % 360
                offset_lat = lat_w + math.cos(math.radians(downwind_dir)) * (offset_dist / 69)
                offset_lon = lon_w + math.sin(math.radians(downwind_dir)) * (offset_dist / (69 * math.cos(math.radians(lat_w))))
                flush_points.append([lat_w, lon_w, final_w])
                flush_points.append([offset_lat, offset_lon, final_w * 0.7])

        if flush_points:
            m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
            folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri").add_to(m)
            HeatMap(flush_points, radius=30, blur=20, max_zoom=12).add_to(m)
            folium.PolyLine(route_points, color="orange", weight=6).add_to(m)

            best_pt = max(flush_points, key=lambda x: x[2])
            folium.Marker([best_pt[0], best_pt[1]], popup="Start Here - Highest Probability", icon=folium.Icon(color="green", icon="star")).add_to(m)

            folium_static(m, width=700, height=500)

            # IDW probability
            s_sum = 0.0
            w_sum = 0.0
            for f_lat, f_lon, w in flush_points:
                d = haversine_distance(center_lat, center_lon, f_lat, f_lon)
                d = max(d, 0.001)
                s_sum += w / (d ** 2)
                w_sum += w
            prob_score = min(100, int((s_sum / w_sum) * 100)) if w_sum > 0 else 0
            st.metric("Route Probability Score", f"{prob_score}%")

            # Encounter rate
            total_flushes = pd.to_numeric(st.session_state.logs["Birds Flushed"], errors='coerce').sum()
            total_miles = pd.to_numeric(st.session_state.logs["Miles Walked"], errors='coerce').sum()
            minutes_per_flush = round((total_miles / 2 * 60) / total_flushes) if total_flushes > 0 else 15

            st.subheader("🎯 AI Hunt Strategy")
            strategy = f"""**Recommended Hunt Plan**
1. Start at the heaviest cluster on downwind side.
2. Walk into the wind to push targets toward blockers.
3. Focus on high-density habitat.
4. Place blockers on downwind edge.
5. Expected encounter rate: 1 bird every {minutes_per_flush} minutes."""
            st.success(strategy)

            # GPX export
            gpx = gpxpy.gpx.GPX()
            wp = gpxpy.gpx.GPXWaypoint(best_pt[0], best_pt[1], name="AI Start")
            gpx.waypoints.append(wp)
            st.download_button("📥 Export AI Start Point (GPX)", data=gpx.to_xml(), file_name="AI_Start.gpx", mime="application/gpx+xml")

            # KML export
            kml = simplekml.Kml()
            for i, (fl, flon, fw) in enumerate(sorted(flush_points, key=lambda x: x[2], reverse=True)[:5]):
                kml.newpoint(name=f"Cluster {i+1}", coords=[(flon, fl)])
            st.download_button("📥 Export Heatmap as KML for onX", data=kml.kml().encode('utf-8'), file_name="AI_Heatmap.kml", mime="application/vnd.google-earth.kml+xml")

            # Shareable link + QR
            if st.button("🔗 Generate Shareable Team Link"):
                share_url = f"https://your-app-url.streamlit.app/?lat={center_lat}&lon={center_lon}&mode={mode}"
                st.code(share_url)
                buf = BytesIO()
                qrcode.make(share_url).save(buf, format="PNG")
                st.image(buf.getvalue(), caption="Scan to share with team")
        else:
            st.info("No flush points found. Add GPX waypoints named 'Flush', 'Bird', or 'Rooster'.")
    else:
        st.info("Import a GPX with flush waypoints to activate AI map.")

st.caption("Built as perfect onX companion • Team mode + multi-species + AI alerts • Full route GPX + KML + QR sharing • Ready for monetization")
