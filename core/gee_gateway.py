"""Google Earth Engine gateway and initialization manager.

Handles authentication, project initialization, and simulation fallback for testing.
"""

import os
import logging
from typing import Optional, Tuple, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    ee = None  # type: ignore


class GEEGateway:
    """Manages Earth Engine lifecycle and connectivity."""

    _initialized: bool = False
    _project: Optional[str] = None
    _simulation_mode: bool = False

    @classmethod
    def initialize(
        cls,
        project_id: Optional[str] = None,
        service_account_key: Optional[str] = None,
        force_simulation: bool = False,
    ) -> bool:
        """Initialize GEE session or fall back gracefully to simulation mode."""
        if force_simulation:
            cls._simulation_mode = True
            logger.info("⚡ Simulation mode explicitly enabled. Running without live GEE server calls.")
            return True

        if not EE_AVAILABLE:
            logger.warning("Earth Engine API library not found. Falling back to simulation mode.")
            cls._simulation_mode = True
            return False

        target_project = project_id or os.getenv("GEE_PROJECT_ID")

        try:
            if service_account_key and os.path.exists(service_account_key):
                credentials = ee.ServiceAccountCredentials(None, key_file=service_account_key)
                ee.Initialize(credentials=credentials, project=target_project)
                logger.info(f"Initialized Earth Engine with service account key on project: {target_project}")
            elif target_project and target_project != "your-gcp-project-id":
                ee.Initialize(project=target_project)
                logger.info(f"Initialized Earth Engine with project: {target_project}")
            else:
                ee.Initialize()
                logger.info("Initialized Earth Engine using default active credentials.")

            cls._initialized = True
            cls._project = target_project
            cls._simulation_mode = False
            return True

        except Exception as e:
            logger.warning(
                f"Failed to connect to Google Earth Engine live service: {e}\n"
                "Switching automatically to local simulation/dry-run mode for pipeline execution."
            )
            cls._simulation_mode = True
            cls._initialized = False
            return False

    @classmethod
    def is_simulation(cls) -> bool:
        return cls._simulation_mode

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized

