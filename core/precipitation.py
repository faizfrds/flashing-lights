"""Dynamic precipitation monitoring using Google Earth Engine satellite feeds.

Integrates JAXA GSMaP Operational (hourly) and NASA GPM IMERG to track
24-hour storm bursts and multi-day antecedent soil saturation.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple

from config import config, RegionPreset
from core.gee_gateway import GEEGateway, EE_AVAILABLE

if EE_AVAILABLE:
    import ee

logger = logging.getLogger(__name__)


class PrecipitationEngine:
    """Manages near-real-time satellite precipitation retrieval."""

    def __init__(self, cfg=config):
        self.cfg = cfg

    def fetch_24h_rainfall(
        self,
        aoi_geom,
        end_time: Optional[datetime] = None,
        hours: int = 24,
    ) -> Any:
        """Fetches accumulated rainfall (in mm) over the specified trailing hours.

        Uses JAXA GSMaP Operational. If empty or unavailable, falls back to GPM IMERG.
        """
        if not EE_AVAILABLE or GEEGateway.is_simulation():
            logger.info(f"[Simulation] Generating synthetic {hours}h convective rainfall field...")
            return {
                "type": "SimulationPrecipitationRaster",
                "hours": hours,
                "peak_mm": 82.5,
                "mean_mm": 34.1,
            }

        end_dt = end_time or datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(hours=hours)

        start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        logger.info(f"Querying GSMaP Operational from {start_str} to {end_str}...")

        gsmap_coll = (
            ee.ImageCollection(self.cfg.precip_gsmap_operational)
            .filterDate(start_str, end_str)
            .select("hourlyPrecipRate")
        )

        # Fallback to GPM IMERG if GSMaP collection is empty for the requested timeframe
        count = gsmap_coll.size().getInfo()
        if count == 0:
            logger.warning("GSMaP Operational returned 0 images for window. Checking GPM IMERG...")
            imerg_coll = (
                ee.ImageCollection(self.cfg.precip_gpm_imerg)
                .filterDate(start_str, end_str)
                .select("precipitationCal")
            )
            count_imerg = imerg_coll.size().getInfo()
            if count_imerg == 0:
                logger.warning(
                    "Near-real-time satellite feeds have typical 12-24h ingest latency. "
                    "Querying latest available observation window..."
                )
                latest_img = ee.Image(
                    ee.ImageCollection(self.cfg.precip_gsmap_operational)
                    .sort("system:time_start", False)
                    .first()
                )
                latest_time_ms = latest_img.get("system:time_start").getInfo()
                latest_dt = datetime.fromtimestamp(latest_time_ms / 1000.0, tz=timezone.utc)
                lat_start_str = (latest_dt - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
                lat_end_str = latest_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                logger.info(f"Using latest available satellite window: {lat_start_str} to {lat_end_str}")
                gsmap_coll = (
                    ee.ImageCollection(self.cfg.precip_gsmap_operational)
                    .filterDate(lat_start_str, lat_end_str)
                    .select("hourlyPrecipRate")
                )
                rainfall = gsmap_coll.sum().clip(aoi_geom).rename("accumulated_rainfall_mm")
                return rainfall

            # GPM IMERG precipitationCal is mm/hr in half-hourly slices -> multiply by 0.5 and sum
            rainfall = imerg_coll.sum().multiply(0.5).clip(aoi_geom).rename("accumulated_rainfall_mm")
            return rainfall

        # GSMaP is hourly mm/hr -> sum equals total mm
        rainfall = gsmap_coll.sum().clip(aoi_geom).rename("accumulated_rainfall_mm")
        return rainfall

    def fetch_antecedent_saturation(
        self,
        aoi_geom,
        days: int = 3,
        end_time: Optional[datetime] = None,
    ) -> Any:
        """Calculates 3-day antecedent precipitation to assess soil water holding saturation."""
        return self.fetch_24h_rainfall(aoi_geom, end_time=end_time, hours=days * 24)

