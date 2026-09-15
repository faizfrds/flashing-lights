"""Static Flash Flood Susceptibility Map calculation using Google Earth Engine.

Combines topography (NASADEM slope) and tree canopy density (Hansen Global Forest Change)
into a normalized 0-100 susceptibility raster.
"""

import logging
from typing import Optional, Dict, Any

from config import config, RegionPreset
from core.gee_gateway import GEEGateway, EE_AVAILABLE

if EE_AVAILABLE:
    import ee

logger = logging.getLogger(__name__)


class SusceptibilityEngine:
    """Calculates static hydrological and geomorphic flash flood susceptibility."""

    def __init__(self, cfg=config):
        self.cfg = cfg

    def get_aoi_geometry(self, region: RegionPreset):
        """Constructs an Earth Engine geometry for the requested region."""
        if not EE_AVAILABLE or GEEGateway.is_simulation():
            return None

        # If administrative filter is available in GAUL
        if region.admin_filter and "adm1_name" in region.admin_filter:
            adm_name = region.admin_filter["adm1_name"]
            gaul = ee.FeatureCollection(self.cfg.admin_level2_dataset)
            aoi_fc = gaul.filter(ee.Filter.eq("ADM1_NAME", adm_name))
            return aoi_fc.geometry()
        elif region.admin_filter and "country_na" in region.admin_filter:
            lsib = ee.FeatureCollection(self.cfg.admin_country_dataset)
            country = lsib.filter(ee.Filter.eq("country_na", "Indonesia"))
            return country.geometry().simplify(1000)

        # Fallback to bounding box rectangle
        min_x, min_y, max_x, max_y = region.bbox
        return ee.Geometry.Rectangle([min_x, min_y, max_x, max_y])

    def compute_slope_score(self, aoi_geom) -> Any:
        """Derives slope from NASADEM and normalizes into 0-100 scale."""
        dem = ee.Image(self.cfg.dem_dataset).select("elevation").clip(aoi_geom)
        slope_deg = ee.Terrain.slope(dem)

        # Steeper terrain (up to max_slope_deg) produces faster runoff upstream
        # Clamp to 1.0 to handle extreme cliff faces
        slope_normalized = slope_deg.divide(self.cfg.max_slope_deg).clamp(0, 1).multiply(100)
        return slope_normalized.rename("slope_score")

    def compute_forest_risk_score(self, aoi_geom) -> Any:
        """Extracts tree canopy density and inverts it (less trees = higher runoff risk)."""
        forest = (
            ee.Image(self.cfg.forest_dataset)
            .select("treecover2000")
            .clip(aoi_geom)
            .unmask(0)
        )

        # Invert: 100% forest canopy = 0 risk, 0% canopy (bare / deforested) = 100 risk
        forest_risk = ee.Image.constant(100).subtract(forest).clamp(0, 100)
        return forest_risk.rename("forest_risk_score")

    def generate_susceptibility_map(self, region: RegionPreset) -> Any:
        """Generates the static composite Flash Flood Susceptibility Map (0-100).

        Formula:
            Risk = (Slope_Score * Weight_Slope) + (Forest_Risk_Score * Weight_Forest)
        """
        if not EE_AVAILABLE or GEEGateway.is_simulation():
            logger.info(f"[Simulation] Generating synthetic susceptibility matrix for {region.name}")
            return {
                "type": "SimulationSusceptibilityRaster",
                "region": region.name,
                "weights": {
                    "slope": self.cfg.weight_slope,
                    "forest": self.cfg.weight_forest,
                },
                "status": "ready",
            }

        aoi_geom = self.get_aoi_geometry(region)

        logger.info(f"Computing NASADEM slope for AOI: {region.name}...")
        slope_score = self.compute_slope_score(aoi_geom)

        logger.info(f"Computing Hansen forest cover risk for AOI: {region.name}...")
        forest_risk = self.compute_forest_risk_score(aoi_geom)

        # Weighted linear combination
        weighted_slope = slope_score.multiply(self.cfg.weight_slope)
        weighted_forest = forest_risk.multiply(self.cfg.weight_forest)

        susceptibility = weighted_slope.add(weighted_forest).rename("flood_risk_index")

        logger.info(
            f"Static Susceptibility Map compiled (Weights: Slope={self.cfg.weight_slope}, Forest={self.cfg.weight_forest})"
        )
        return susceptibility

