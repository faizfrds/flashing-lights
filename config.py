"""Configuration settings and region presets for the Flash Flood Early Warning System (FFEWS)."""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class RegionPreset:
    """Predefined bounding boxes or administrative names for fast testing and targeting."""
    name: str
    description: str
    # Bounding Box: [min_lon, min_lat, max_lon, max_lat]
    bbox: list[float]
    admin_filter: Optional[Dict[str, str]] = None


# Standard AOI Presets in Indonesia
REGION_PRESETS: Dict[str, RegionPreset] = {
    "indonesia": RegionPreset(
        name="Indonesia National",
        description="Entire Indonesian Archipelago",
        bbox=[95.0, -11.0, 141.0, 6.0],
        admin_filter={"country_na": "Indonesia"},
    ),
    "west_java": RegionPreset(
        name="West Java & Greater Jakarta",
        description="Jabodetabekpunjur & Ciliwung Basin flash flood corridor",
        bbox=[106.3, -7.8, 108.8, -5.9],
        admin_filter={"adm1_name": "Jawa Barat"},
    ),
    "dki_jakarta": RegionPreset(
        name="DKI Jakarta",
        description="Special Capital Region of Jakarta",
        bbox=[106.68, -6.37, 106.98, -6.08],
        admin_filter={"adm1_name": "Dki Jakarta"},
    ),
    "north_sumatra": RegionPreset(
        name="North Sumatra",
        description="North Sumatra mountainous and riverine catchments",
        bbox=[97.0, 0.5, 100.5, 4.3],
        admin_filter={"adm1_name": "Sumatera Utara"},
    ),
    "bali": RegionPreset(
        name="Bali Island",
        description="Bali river catchments and volcanic slopes",
        bbox=[114.4, -8.9, 115.8, -8.0],
        admin_filter={"adm1_name": "Bali"},
    ),
}


@dataclass
class FFEWSConfig:
    """Master configuration for the FFEWS detection pipeline."""

    # GEE Project Configuration
    gee_project: str = os.getenv("GEE_PROJECT_ID", "your-gcp-project-id")
    gee_service_account: Optional[str] = os.getenv("GEE_SERVICE_ACCOUNT_KEY", None)

    # GEE Datasets
    dem_dataset: str = "NASA/NASADEM_HGT/001"
    forest_dataset: str = "UMD/hansen/global_forest_change_2024_v1_12"
    worldcover_dataset: str = "ESA/WorldCover/v200"
    precip_gsmap_operational: str = "JAXA/GPM_L3/GSMaP/v6/operational"
    precip_gpm_imerg: str = "NASA/GPM_L3/IMERG_V07"
    admin_country_dataset: str = "USDOS/LSIB_SIMPLE/2017"
    admin_level2_dataset: str = "FAO/GAUL/2015/level2"  # Regencies/Kabupaten/Kota

    # Susceptibility Modeling Weights
    # Multi-Criteria Evaluation (MCE): slope weight + forest cover weight = 1.0
    weight_slope: float = 0.55
    weight_forest: float = 0.45
    max_slope_deg: float = 45.0

    # Risk Thresholds
    susceptibility_alert_threshold: float = float(
        os.getenv("SUSCEPTIBILITY_ALERT_THRESHOLD", "70.0")
    )
    critical_rainfall_mm: float = float(
        os.getenv("CRITICAL_RAINFALL_MM", "50.0")
    )
    antecedent_rainfall_threshold: float = float(
        os.getenv("ANTECEDENT_RAINFALL_THRESHOLD", "100.0")
    )

    # Vectorization & Scale
    analysis_scale_m: int = 500  # Resolution in meters for regional aggregation
    min_cluster_area_ha: float = float(os.getenv("MIN_CLUSTER_AREA_HA", "25.0"))

    # Alert Notification Integrations
    telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
    discord_webhook_url: Optional[str] = os.getenv("DISCORD_WEBHOOK_URL")
    custom_webhook_url: Optional[str] = os.getenv("CUSTOM_WEBHOOK_URL")

    # Active Region
    default_region: str = os.getenv("DEFAULT_REGION", "west_java")

    def get_region(self, region_key: Optional[str] = None) -> RegionPreset:
        key = (region_key or self.default_region).lower()
        if key not in REGION_PRESETS:
            raise KeyError(
                f"Unknown region '{key}'. Available presets: {list(REGION_PRESETS.keys())}"
            )
        return REGION_PRESETS[key]


# Default singleton instance
config = FFEWSConfig()

