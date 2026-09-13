"""Interactive HTML Leaflet Map Generator for Indonesia Flash Flood Early Warning System.

Generates self-contained, responsive map dashboards displaying active alert polygons,
susceptibility zones, rainfall metrics, and administrative boundaries.
"""

import json
import logging
from typing import List, Dict, Any, Optional

from config import RegionPreset
from core.alert_engine import AlertHotspot

logger = logging.getLogger(__name__)


class MapGenerator:
    """Generates interactive Leaflet map dashboards."""

    @staticmethod
    def generate_html_map(
        hotspots: List[AlertHotspot],
        region: RegionPreset,
        output_html_path: str,
    ) -> str:
        """Renders an interactive map HTML document visualizing the alert hotspots."""

        # Calculate map center from region bbox
        min_lon, min_lat, max_lon, max_lat = region.bbox
        center_lat = (min_lat + max_lat) / 2.0
        center_lon = (min_lon + max_lon) / 2.0

        # Build GeoJSON FeatureCollection from hotspots
        features = []
        for h in hotspots:
            features.append({
                "type": "Feature",
                "properties": {
                    "hotspot_id": h.hotspot_id,
                    "severity": h.severity,
                    "province": h.province,
                    "regency": h.regency,
                    "district": h.district or "-",
                    "rainfall_mm": h.estimated_rainfall_mm,
                    "susceptibility_index": h.susceptibility_index,
                    "area_hectares": h.area_hectares,
                    "timestamp": h.timestamp,
                },
                "geometry": h.coordinates_geojson,
            })

        geojson_str = json.dumps({"type": "FeatureCollection", "features": features})

        # Precompute summary statistics
        total_alerts = len(hotspots)
        peak_rain = max([h.estimated_rainfall_mm for h in hotspots], default=0.0)
        critical_count = sum(1 for h in hotspots if h.severity == "CRITICAL")
        high_count = sum(1 for h in hotspots if h.severity == "HIGH")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Indonesia FFEWS - Flash Flood Early Warning Dashboard</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: 'Inter', sans-serif;
      background: #0f172a;
      color: #f8fafc;
      overflow: hidden;
    }}
    #map {{
      height: 100vh;
      width: 100vw;
      z-index: 1;
    }}
    .header-panel {{
      position: absolute;
      top: 16px;
      left: 16px;
      z-index: 1000;
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(12px);
      padding: 16px 20px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
      max-width: 420px;
    }}
    .title-row {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
    }}
    .pulse-dot {{
      width: 12px;
      height: 12px;
      background-color: #ef4444;
      border-radius: 50%;
      box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
      animation: pulse 1.8s infinite;
    }}
    @keyframes pulse {{
      0% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
      70% {{ box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
    }}
    h1 {{
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: #ffffff;
    }}
    .subhead {{
      font-size: 12px;
      color: #94a3b8;
      margin-bottom: 12px;
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-bottom: 8px;
    }}
    .stat-card {{
      background: rgba(30, 41, 59, 0.7);
      padding: 8px 10px;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.05);
      text-align: center;
    }}
    .stat-val {{
      font-size: 18px;
      font-weight: 700;
      color: #38bdf8;
    }}
    .stat-val.crit {{
      color: #ef4444;
    }}
    .stat-lbl {{
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #94a3b8;
      margin-top: 2px;
    }}
    .legend-panel {{
      position: absolute;
      bottom: 20px;
      right: 20px;
      z-index: 1000;
      background: rgba(15, 23, 42, 0.88);
      backdrop-filter: blur(12px);
      padding: 14px 18px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      font-size: 12px;
    }}
    .legend-title {{
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #94a3b8;
      margin-bottom: 8px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }}
    .color-chip {{
      width: 16px;
      height: 16px;
      border-radius: 4px;
    }}
    .leaflet-popup-content-wrapper {{
      background: #1e293b;
      color: #f8fafc;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      box-shadow: 0 10px 20px rgba(0,0,0,0.4);
    }}
    .leaflet-popup-tip {{
      background: #1e293b;
    }}
    .popup-title {{
      font-size: 14px;
      font-weight: 700;
      color: #ef4444;
      margin-bottom: 6px;
    }}
    .popup-table {{
      font-size: 12px;
      width: 100%;
      border-collapse: collapse;
    }}
    .popup-table td {{
      padding: 3px 0;
    }}
    .popup-table td:first-child {{
      color: #94a3b8;
      width: 45%;
    }}
  </style>
</head>
<body>

  <div class="header-panel">
    <div class="title-row">
      <div class="pulse-dot"></div>
      <h1>Indonesia Flash Flood Early Warning</h1>
    </div>
    <div class="subhead">Region: <b>{region.name}</b> | Sentinel Operational Run</div>
    
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-val crit">{total_alerts}</div>
        <div class="stat-lbl">Active Hotspots</div>
      </div>
      <div class="stat-card">
        <div class="stat-val">{peak_rain:.1f} <span style="font-size:11px">mm</span></div>
        <div class="stat-lbl">Peak 24h Rain</div>
      </div>
      <div class="stat-card">
        <div class="stat-val">{critical_count}</div>
        <div class="stat-lbl">Siaga 1 Zones</div>
      </div>
    </div>
    <div style="font-size: 11px; color: #64748b; margin-top: 4px;">
      Data sources: NASA NASADEM &bullet; Hansen Global Forest &bullet; JAXA GSMaP
    </div>
  </div>

  <div class="legend-panel">
    <div class="legend-title">Risk Severity Index</div>
    <div class="legend-item">
      <div class="color-chip" style="background: #ef4444;"></div>
      <span>Critical (Siaga 1) &bull; Rain &gt; 80mm</span>
    </div>
    <div class="legend-item">
      <div class="color-chip" style="background: #f97316;"></div>
      <span>High Alert &bull; Rain &gt; 50mm + Slope</span>
    </div>
    <div class="legend-item">
      <div class="color-chip" style="background: #eab308;"></div>
      <span>Moderate &bull; Rain &gt; 40mm</span>
    </div>
  </div>

  <div id="map"></div>

  <script>
    const map = L.map('map').setView([{center_lat}, {center_lon}], 9);

    // CartoDB Dark Matter Basemap
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>, &copy; OpenStreetMap contributors',
      subdomains: 'abcd',
      maxZoom: 19
    }}).addTo(map);

    const hotspotsData = {geojson_str};

    function getStyle(feature) {{
      const sev = feature.properties.severity;
      let color = '#ef4444';
      if (sev === 'HIGH') color = '#f97316';
      if (sev === 'MODERATE') color = '#eab308';

      return {{
        color: color,
        weight: 2,
        opacity: 0.9,
        fillColor: color,
        fillOpacity: 0.45
      }};
    }}

    function onEachFeature(feature, layer) {{
      const p = feature.properties;
      const html = `
        <div class="popup-title">🚨 Flash Flood Hotspot</div>
        <table class="popup-table">
          <tr><td>ID Kejadian:</td><td><b>${{p.hotspot_id}}</b></td></tr>
          <tr><td>Status:</td><td><b style="color:${{p.severity === 'CRITICAL' ? '#ef4444' : '#f97316'}}">${{p.severity}}</b></td></tr>
          <tr><td>Kabupaten/Kota:</td><td><b>${{p.regency}}</b></td></tr>
          <tr><td>Provinsi:</td><td>${{p.province}}</td></tr>
          <tr><td>Sub-DAS:</td><td>${{p.district}}</td></tr>
          <tr><td>Curah Hujan 24h:</td><td><b>${{p.rainfall_mm}} mm</b></td></tr>
          <tr><td>Indeks Kerentanan:</td><td><b>${{p.susceptibility_index}} / 100</b></td></tr>
          <tr><td>Luas Area:</td><td>${{p.area_hectares}} ha</td></tr>
        </table>
      `;
      layer.bindPopup(html);
    }}

    if (hotspotsData.features && hotspotsData.features.length > 0) {{
      const geojsonLayer = L.geoJSON(hotspotsData, {{
        style: getStyle,
        onEachFeature: onEachFeature
      }}).addTo(map);

      map.fitBounds(geojsonLayer.getBounds(), {{ padding: [60, 60] }});
    }}
  </script>
</body>
</html>
"""

        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Dashboard HTML generated at: {output_html_path}")
        return output_html_path

