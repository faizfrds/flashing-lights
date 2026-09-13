"""FastAPI Cloud Service for Google Cloud Run / Container deployments.

Provides:
- GET /            : Healthcheck & system status
- POST /trigger    : Scheduled endpoint called by Google Cloud Scheduler
- GET /map         : Serves live interactive Leaflet flood map
- GET /alerts.geojson : Serves latest vectorized flood alert polygons
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, Response
from fastapi.responses import HTMLResponse, JSONResponse

from config import config
from main import run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFEWS-CloudApp")

app = FastAPI(
    title="Indonesia Flash Flood Early Warning System (FFEWS)",
    description="Automated GEE Hydrological Monitoring Service",
    version="1.0.0",
)

GEOJSON_PATH = "/tmp/active_flood_alerts.geojson"
MAP_HTML_PATH = "/tmp/index.html"


@app.get("/")
def healthcheck():
    """Healthcheck endpoint for Cloud Run and load balancers."""
    return {
        "status": "online",
        "service": "Indonesia FFEWS",
        "project": config.gee_project,
        "default_region": config.default_region,
        "utc_time": datetime.now(timezone.utc).isoformat(),
    }


@app.api_route("/trigger", methods=["GET", "POST"])
def trigger_monitoring(region: str = None, dispatch: bool = True):
    """Execution endpoint triggered by Google Cloud Scheduler every 1-3 hours."""
    target_region = region or config.default_region
    logger.info(f"Triggering monitoring run for region: {target_region}")

    try:
        hotspots = run_pipeline(
            region_key=target_region,
            project_id=config.gee_project,
            rain_threshold=config.critical_rainfall_mm,
            susc_threshold=config.susceptibility_alert_threshold,
            force_simulation=False,
            geojson_path=GEOJSON_PATH,
            map_html_path=MAP_HTML_PATH,
            dispatch_alerts=dispatch,
        )

        return {
            "status": "completed",
            "region": target_region,
            "hotspots_detected": len(hotspots),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alerts": [h.to_dict() for h in hotspots],
        }
    except Exception as e:
        logger.error(f"Execution failure during scheduled trigger: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@app.get("/map", response_class=HTMLResponse)
def get_live_map():
    """Serves the latest rendered Leaflet dashboard."""
    if os.path.exists(MAP_HTML_PATH):
        with open(MAP_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    elif os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h3>No active map generated yet. Please run /trigger first.</h3>")


@app.get("/alerts.geojson")
def get_geojson():
    """Serves the latest GeoJSON alert polygon file."""
    path = GEOJSON_PATH if os.path.exists(GEOJSON_PATH) else "active_flood_alerts.geojson"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/geo+json")
    return JSONResponse(status_code=404, content={"message": "No GeoJSON data available"})

