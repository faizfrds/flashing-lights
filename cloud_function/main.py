"""Google Cloud Function entrypoint for automated hourly/cron execution.

Can be deployed to Google Cloud Functions (2nd gen) or Cloud Run and triggered
by Google Cloud Scheduler every 3-6 hours.
"""

import os
import json
import logging
from datetime import datetime, timezone

from config import config
from main import run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FFEWS-CloudFunction")


def flood_alert_cron_handler(request=None):
    """Cloud Function entrypoint for HTTP or Pub/Sub scheduled events."""
    logger.info("Cloud Function invoked by Cloud Scheduler.")

    region = os.getenv("TARGET_REGION", config.default_region)
    project_id = os.getenv("GEE_PROJECT_ID", config.gee_project)

    try:
        hotspots = run_pipeline(
            region_key=region,
            project_id=project_id,
            rain_threshold=config.critical_rainfall_mm,
            susc_threshold=config.susceptibility_alert_threshold,
            force_simulation=False,  # In production Cloud Function, runs live
            geojson_path="/tmp/active_flood_alerts.geojson",
            map_html_path="/tmp/index.html",
            dispatch_alerts=True,
        )

        response_payload = {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "region": region,
            "detected_hotspots": len(hotspots),
            "alerts": [h.to_dict() for h in hotspots],
        }
        return (json.dumps(response_payload), 200, {"Content-Type": "application/json"})

    except Exception as e:
        logger.error(f"Error executing FFEWS automated cron: {e}", exc_info=True)
        return (json.dumps({"status": "error", "message": str(e)}), 500, {"Content-Type": "application/json"})

