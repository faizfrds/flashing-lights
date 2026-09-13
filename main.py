"""CLI Pipeline Entrypoint for Indonesia Flash Flood Early Warning System (FFEWS).

Orchestrates:
1. GEE session initialization
2. Static Susceptibility Map calculation (Slope + Forest Cover)
3. Dynamic Precipitation calculation (GSMaP / GPM)
4. Compound Risk Alert Evaluation & Hotspot Vectorization
5. Administrative Boundary (Kabupaten/Kota) Intersection
6. GeoJSON export & Interactive Leaflet Dashboard rendering
7. Automated Alert Dispatch (Telegram / Discord / Webhooks)
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timezone

from config import config, REGION_PRESETS
from core.gee_gateway import GEEGateway
from core.susceptibility import SusceptibilityEngine
from core.precipitation import PrecipitationEngine
from core.alert_engine import AlertEngine
from notifications.dispatcher import AlertDispatcher
from web.map_generator import MapGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("FFEWS-Main")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Indonesia Flash Flood Early Warning System (FFEWS) - GEE Engine"
    )
    parser.add_argument(
        "--region",
        type=str,
        default=config.default_region,
        choices=list(REGION_PRESETS.keys()),
        help=f"Target region preset (default: {config.default_region})",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=config.gee_project,
        help="Google Cloud Project ID for Earth Engine API",
    )
    parser.add_argument(
        "--rain-thresh",
        type=float,
        default=config.critical_rainfall_mm,
        help="24-hour critical rainfall threshold in mm (default: 50.0)",
    )
    parser.add_argument(
        "--susc-thresh",
        type=float,
        default=config.susceptibility_alert_threshold,
        help="Static flood susceptibility threshold 0-100 (default: 70.0)",
    )
    parser.add_argument(
        "--dry-run",
        "--simulate",
        action="store_true",
        help="Run in local simulation mode (does not call live GEE servers)",
    )
    parser.add_argument(
        "--export-geojson",
        type=str,
        default="active_flood_alerts.geojson",
        help="Output GeoJSON file path for vectorized alert hotspots",
    )
    parser.add_argument(
        "--export-map",
        type=str,
        default="index.html",
        help="Output HTML path for interactive Leaflet dashboard",
    )
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help="Dispatch active alerts to configured notification channels (Telegram/Discord)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in the background at regular intervals",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=180,
        help="Interval in minutes between checks when running in --daemon mode (default: 180 min / 3 hours)",
    )
    return parser.parse_args()


def run_pipeline(
    region_key: str = "west_java",
    project_id: str = "your-gcp-project-id",
    rain_threshold: float = 50.0,
    susc_threshold: float = 70.0,
    force_simulation: bool = False,
    geojson_path: str = "active_flood_alerts.geojson",
    map_html_path: str = "index.html",
    dispatch_alerts: bool = False,
):
    print("=" * 65)
    print(" 🌊 INDONESIA FLASH FLOOD EARLY WARNING SYSTEM (FFEWS)")
    print(" Combining NASADEM + Hansen Forest Cover + JAXA GSMaP in GEE")
    print("=" * 65)

    region = config.get_region(region_key)
    logger.info(f"Target Region: {region.name} ({region.description})")
    logger.info(f"Bounding Box: {region.bbox}")

    # 1. Initialize Earth Engine Gateway
    GEEGateway.initialize(project_id=project_id, force_simulation=force_simulation)
    is_sim = GEEGateway.is_simulation()

    # 2. Compute Static Susceptibility Map
    susc_engine = SusceptibilityEngine(config)
    susceptibility_map = susc_engine.generate_susceptibility_map(region)
    aoi_geom = susc_engine.get_aoi_geometry(region)

    # 3. Ingest Dynamic Precipitation
    precip_engine = PrecipitationEngine(config)
    precip_image = precip_engine.fetch_24h_rainfall(aoi_geom, hours=24)

    # 4. Evaluate Compound Alert Risk & Vectorize Hotspots
    alert_engine = AlertEngine(config)
    alert_mask = alert_engine.evaluate_risk_mask(
        susceptibility_map=susceptibility_map,
        rainfall_image=precip_image,
        rainfall_thresh=rain_threshold,
        susceptibility_thresh=susc_threshold,
    )

    hotspots = alert_engine.vectorize_and_intersect(
        alert_mask=alert_mask,
        region=region,
        aoi_geom=aoi_geom,
    )

    print("\n" + "-" * 65)
    print(f"📊 ALERT ENGINE SUMMARY: {len(hotspots)} ACTIVE HOTSPOT(S) DETECTED")
    print("-" * 65)

    for h in hotspots:
        status_icon = "🔴" if h.severity == "CRITICAL" else "🟠"
        print(f"{status_icon} [{h.severity}] {h.regency}, {h.province} ({h.district or 'Catchment'})")
        print(f"   • Est. 24h Rain: {h.estimated_rainfall_mm:.1f} mm | Susceptibility: {h.susceptibility_index:.1f}/100")
        print(f"   • Impact Area: {h.area_hectares:.1f} ha | Hotspot ID: {h.hotspot_id}")

    # 5. Export GeoJSON
    if geojson_path:
        alert_engine.export_geojson(hotspots, geojson_path)

    # 6. Render Interactive Dashboard Map
    if map_html_path:
        MapGenerator.generate_html_map(hotspots, region, map_html_path)

    # 7. Dispatch Notifications
    if dispatch_alerts:
        dispatcher = AlertDispatcher(config)
        res = dispatcher.dispatch(hotspots)
        logger.info(f"Notification dispatch completed: {res}")

    print("-" * 65)
    print(f"✅ Pipeline completed successfully at {datetime.now(timezone.utc).isoformat()}")
    print(f"📁 Dashboard Map: {os.path.abspath(map_html_path)}")
    print(f"📁 GeoJSON Layer: {os.path.abspath(geojson_path)}")
    print("=" * 65 + "\n")
    return hotspots


def main():
    args = parse_args()

    if not args.daemon:
        run_pipeline(
            region_key=args.region,
            project_id=args.project,
            rain_threshold=args.rain_thresh,
            susc_threshold=args.susc_thresh,
            force_simulation=args.dry_run,
            geojson_path=args.export_geojson,
            map_html_path=args.export_map,
            dispatch_alerts=args.dispatch,
        )
        return

    import time
    logger.info(
        f"🔁 Continuous Daemon Mode active. Checking region '{args.region}' every {args.interval_minutes} minutes..."
    )
    iteration = 1
    while True:
        try:
            logger.info(f"--- Cycle #{iteration} starting at {datetime.now(timezone.utc).isoformat()} ---")
            run_pipeline(
                region_key=args.region,
                project_id=args.project,
                rain_threshold=args.rain_thresh,
                susc_threshold=args.susc_thresh,
                force_simulation=args.dry_run,
                geojson_path=args.export_geojson,
                map_html_path=args.export_map,
                dispatch_alerts=args.dispatch,
            )
            iteration += 1
        except Exception as e:
            logger.error(f"Error encountered during monitoring cycle: {e}", exc_info=True)

        logger.info(f"Sleeping for {args.interval_minutes} minutes until next cycle...")
        time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    main()

