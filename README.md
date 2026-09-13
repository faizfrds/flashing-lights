# 🌊 Indonesia Flash Flood Early Warning System (FFEWS)

An automated hydrological early warning system for Indonesia developed in Python and **Google Earth Engine (GEE)**. FFEWS combines static environmental susceptibility factors (topographic slope from NASADEM and forest canopy friction from Hansen Global Forest Change) with dynamic near-real-time satellite precipitation (JAXA GSMaP Operational and NASA GPM IMERG) to generate spatial alert polygons and notify administrative disaster responders (BPBD).

---

## 🏛️ Architecture Overview

```
[ GEE Satellite Ingestion ]
    ├── NASADEM (30m DEM -> Normalized Slope)
    ├── Hansen Global Forest Change (Canopy Friction Index)
    └── JAXA GSMaP Operational (Near-Real-Time Hourly Precipitation)
            │
            ▼
[ Compound Risk Matrix ]
    ├── Static Susceptibility Map (0-100 Risk Scale)
    └── Dynamic Extreme Rainfall Trigger (24h > 50mm)
            │
            ▼
[ Hotspot Vectorization & Admin Overlay ]
    ├── ee.Image.reduceToVectors (Cluster Extraction)
    ├── Noise Filtering (Area >= 25 Hectares)
    └── Spatial Intersect with FAO GAUL Level 2 (Kabupaten / Kota)
            │
            ├──> [ Interactive Leaflet Dashboard (index.html) ]
            ├──> [ GeoJSON Hazard Layer (active_flood_alerts.geojson) ]
            └──> [ Emergency Alerts: Telegram Bot / Discord / Webhooks ]
```

---

## 📁 Repository Structure

```
flashflood-detection/
├── config.py                 # Region presets (West Java, Jakarta, Sumatra, etc.) and thresholds
├── main.py                   # Main CLI pipeline orchestrator
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── core/
│   ├── gee_gateway.py        # Earth Engine authentication and simulation manager
│   ├── susceptibility.py     # Static NASADEM slope & forest risk index
│   ├── precipitation.py      # GSMaP / GPM precipitation ingestion
│   └── alert_engine.py       # reduceToVectors clustering & GAUL admin intersection
├── notifications/
│   ├── telegram.py           # Bilingual (ID/EN) Telegram Bot emergency alerts
│   ├── webhook.py            # Discord embed and generic JSON webhooks
│   └── dispatcher.py         # Multi-channel alert dispatcher
├── web/
│   └── map_generator.py      # Interactive Leaflet web map dashboard
├── cloud_function/
│   └── main.py               # Headless handler for Google Cloud Functions / Cloud Run
└── tests/
    └── test_ffews.py         # Pytest verification suite
```

---

## 🚀 Quick Start

### 1. Installation

Clone and install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Set your Google Cloud project and notification credentials in `.env`:
```ini
GEE_PROJECT_ID=your-gcp-project-id
DEFAULT_REGION=west_java
CRITICAL_RAINFALL_MM=50.0
SUSCEPTIBILITY_ALERT_THRESHOLD=70.0
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=-1001234567890
```

---

## 💻 CLI Usage

### Run Live Pipeline for West Java
```bash
python3 main.py --region west_java --project your-gcp-project-id
```

### Run in Offline / Simulated Mode (Test Without Active GEE Credentials)
```bash
python3 main.py --region west_java --dry-run
```

### Run Continuous Background Monitoring
```bash
# Poll satellite feeds and update alerts every 60 minutes
python3 main.py --region west_java --dispatch --daemon --interval-minutes 60

# Run in background detached from terminal (Mac/Linux)
nohup python3 main.py --region west_java --dispatch --daemon --interval-minutes 180 > ffews.log 2>&1 &
```

### Options & Flags
- `--region`: Target catchment (`west_java`, `dki_jakarta`, `north_sumatra`, `bali`, `indonesia`).
- `--rain-thresh`: Critical 24-hour rainfall threshold in mm (default: `50.0`).
- `--susc-thresh`: Static susceptibility index trigger 0-100 (default: `70.0`).
- `--daemon`: Enable continuous background polling loop.
- `--interval-minutes`: Interval between monitoring cycles when `--daemon` is active (default: `180` min / 3 hours).
- `--export-geojson`: Path to output GeoJSON feature collection (default: `active_flood_alerts.geojson`).
- `--export-map`: Path to output interactive HTML dashboard (default: `index.html`).
- `--dispatch`: Broadcast active warnings to configured Telegram and Discord channels.

---

## 🗺️ Interactive Dashboard

When running `main.py`, an interactive Leaflet map (`index.html`) is rendered automatically with:
- Dark-mode CartoDB basemap
- Active alert polygons color-coded by severity (**Critical / Siaga 1** in red, **High Alert** in orange)
- Summary statistics card (Active Hotspots, Peak 24h Rain, Critical Zones)
- Interactive popup cards with incident IDs, Kabupaten/Kota, estimated precipitation, and BPBD mitigation guidance.

To view the dashboard, open `index.html` in your browser.

---

## ⏰ Automated Cloud Deployment

To automate the monitor every 3 hours using Google Cloud:

1. **Deploy to Cloud Functions (2nd gen)**:
```bash
gcloud functions deploy ffews-monitor \
    --gen2 \
    --runtime python310 \
    --entry-point flood_alert_cron_handler \
    --source . \
    --trigger-http \
    --set-env-vars GEE_PROJECT_ID=your-gcp-project-id,TARGET_REGION=west_java
```

2. **Schedule with Google Cloud Scheduler (Every 3 hours)**:
```bash
gcloud scheduler jobs create http ffews-hourly-job \
    --schedule="0 */3 * * *" \
    --uri="https://REGION-PROJECT_ID.cloudfunctions.net/ffews-monitor" \
    --http-method=POST
```

