# Line Node Processor

QGIS 3.28 Processing-only plugin for sampling points along line features at fixed intervals, with optional vertex preservation, azimuth calculation, 2D/3D length computation, and elevation sampling from a GeoTIFF.

## Features
- **Fixed distance sampling** (meters) along line geometries.
- **Preserve original vertices** as additional sample points.
- **KP (chainage) and azimuth** computation.
- **2D and 3D segment lengths**, with cumulative 3D length.
- **Elevation sampling** from raster layers (GeoTIFF, etc.).
- **Group-based export**: separate CSV/Shapefile for each group value.
- **CRS validation**: blocks geographic CRS or non-meter map units.
- Works with **existing QGIS layers** or **external files**.

## Installation
1. Download or build `line_node_processor.zip`.
2. In QGIS, go to **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select `line_node_processor.zip` and install.

## Usage
1. Open **Processing Toolbox** in QGIS.
2. Find **Line Node Processor** under *Line Tools*.
3. Set:
   - **Input line layer**
   - Optional **Elevation raster**
   - Optional **Group field**
   - **Sampling distance** (meters)
   - Whether to **Preserve vertices**
   - Whether to **Preserve original attributes**
   - Output folder
4. Run the algorithm — results are exported to CSV and optionally Shapefile.

## Output
For each group:
- `{group}_{distance}_node.csv`
- `{group}_{distance}_node.shp` (if enabled)

Columns include:
- Longitude, Latitude, Easting, Northing
- Elevation
- Distance (2D), Length_3D
- Azimuth
- KP (chainage)
- Total_3D_Length
- Group field or `Group` column
- Preserved attributes (if enabled)

## Requirements
- QGIS **3.28 LTR**
- PyQGIS (bundled with QGIS)
