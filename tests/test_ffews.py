"""Unit test suite for Indonesia Flash Flood Early Warning System (FFEWS)."""

import os
import json
import tempfile
import pytest

from config import config, REGION_PRESETS
from core.gee_gateway import GEEGateway
from core.susceptibility import SusceptibilityEngine
from core.precipitation import PrecipitationEngine
from core.alert_engine import AlertEngine, AlertHotspot
from notifications.telegram import TelegramNotifier
from notifications.webhook import WebhookNotifier
from web.map_generator import MapGenerator
from main import run_pipeline


def test_region_presets():
    assert "indonesia" in REGION_PRESETS
    assert "west_java" in REGION_PRESETS
    assert "dki_jakarta" in REGION_PRESETS

    region = config.get_region("west_java")
    assert len(region.bbox) == 4
    min_lon, min_lat, max_lon, max_lat = region.bbox
    assert min_lon < max_lon
    assert min_lat < max_lat


def test_gee_gateway_simulation():
    GEEGateway.initialize(force_simulation=True)
    assert GEEGateway.is_simulation() is True


def test_susceptibility_simulation():
    GEEGateway.initialize(force_simulation=True)
    susc_engine = SusceptibilityEngine(config)
    region = config.get_region("west_java")
    result = susc_engine.generate_susceptibility_map(region)
    assert result is not None
    assert result["type"] == "SimulationSusceptibilityRaster"


def test_precipitation_simulation():
    GEEGateway.initialize(force_simulation=True)
    precip_engine = PrecipitationEngine(config)
    rain = precip_engine.fetch_24h_rainfall(None, hours=24)
    assert rain["peak_mm"] > 50.0


def test_alert_engine_vectorization_simulation():
    GEEGateway.initialize(force_simulation=True)
    alert_engine = AlertEngine(config)
    region = config.get_region("west_java")

    hotspots = alert_engine.vectorize_and_intersect(
        alert_mask=None,
        region=region,
        aoi_geom=None,
    )

    assert len(hotspots) >= 2
    for h in hotspots:
        assert h.province == "Jawa Barat"
        assert h.estimated_rainfall_mm > 50.0
        assert h.area_hectares > 0
        assert "type" in h.coordinates_geojson


def test_geojson_export():
    alert_engine = AlertEngine(config)
    region = config.get_region("west_java")
    hotspots = alert_engine.vectorize_and_intersect(None, region, None)

    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        data = alert_engine.export_geojson(hotspots, tmp_path)
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == len(hotspots)

        with open(tmp_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded["type"] == "FeatureCollection"
            assert len(loaded["features"]) == len(hotspots)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_telegram_message_formatting():
    notifier = TelegramNotifier()
    hotspot = AlertHotspot(
        hotspot_id="FF-IDN-TEST",
        severity="CRITICAL",
        province="Jawa Barat",
        regency="Kabupaten Bogor",
        district="Puncak Headwaters",
        estimated_rainfall_mm=95.0,
        susceptibility_index=88.5,
        area_hectares=410.0,
    )

    msg = notifier.format_alert_message(hotspot)
    assert "PERINGATAN DINI BANJIR BANDANG" in msg
    assert "Kabupaten Bogor" in msg
    assert "95.0 mm" in msg
    assert "SIAGA 1" in msg


def test_map_generation():
    alert_engine = AlertEngine(config)
    region = config.get_region("west_java")
    hotspots = alert_engine.vectorize_and_intersect(None, region, None)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        MapGenerator.generate_html_map(hotspots, region, tmp_path)
        assert os.path.exists(tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            html = f.read()
            assert "Indonesia Flash Flood Early Warning" in html
            assert "leaflet" in html.lower()
            assert "Kabupaten Bogor" in html
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_full_pipeline_run():
    with tempfile.TemporaryDirectory() as tmp_dir:
        geojson_file = os.path.join(tmp_dir, "alerts.geojson")
        map_file = os.path.join(tmp_dir, "map.html")

        hotspots = run_pipeline(
            region_key="west_java",
            project_id="test-project",
            force_simulation=True,
            geojson_path=geojson_file,
            map_html_path=map_file,
            dispatch_alerts=False,
        )

        assert len(hotspots) > 0
        assert os.path.exists(geojson_file)
        assert os.path.exists(map_file)

