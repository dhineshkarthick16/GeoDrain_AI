# GeoDrainAI — Technology Stack

## 1. Programming Language

### Python 3.12

Python is used as the primary language for:

* Geospatial processing
* AI/ML models
* Hydrological analysis
* Hydraulic calculations
* Route optimization
* Report generation
* Backend services

---

## 2. Geospatial Processing

### Rasterio

Used for:

* Reading GeoTIFF files
* DEM processing
* Raster analysis
* Elevation data handling

### GeoPandas

Used for:

* Vector GIS data
* GeoJSON processing
* Shapefile processing
* Spatial analysis

### Shapely

Used for:

* Geometry operations
* Lines
* Polygons
* Buffers
* Intersections

### PyProj

Used for:

* Coordinate reference systems
* Projection conversion
* Latitude/longitude transformations

### Fiona

Used for:

* Reading and writing GIS vector files

---

## 3. Terrain and Hydrology

### NumPy

Used for:

* Raster array processing
* Numerical calculations
* Terrain matrices

### SciPy

Planned for:

* Scientific calculations
* Spatial algorithms
* Terrain processing

### WhiteboxTools / PySheds

Planned for:

* Sink filling
* Flow direction
* Flow accumulation
* Watershed analysis
* Stream extraction

---

## 4. Artificial Intelligence and Machine Learning

### Computer Vision

Planned models:

* Segmentation models
* Lightweight CNN models
* Semantic land-cover classification

Target classes:

```text
Building
Road
Water Body
Vegetation
Open Land
```

### Machine Learning

Primary model:

**XGBoost**

Used for:

* Flood risk prediction
* Feature importance
* Risk classification

Potential features:

```text
Elevation
Slope
Flow Accumulation
Rainfall
Land Cover
Distance to Drainage
```

---

## 5. Optimization

### NetworkX

Used for:

* Drainage network modelling
* Graph-based route optimization
* Drainage connectivity

### A* / Cost-Surface Optimization

Used for:

* Finding practical drainage routes
* Avoiding buildings
* Reducing road crossings
* Minimizing construction cost

---

## 6. Hydraulic Modelling

GeoDrainAI will generate hydraulic model-ready inputs from geospatial data.

The hydraulic module will handle:

* Drainage centerlines
* Cross-section generation
* Elevation profiles
* Channel geometry
* Manning roughness values
* Design flow estimation

The system will provide a bridge to:

**HEC-RAS-compatible hydraulic modelling workflows**

GeoDrainAI is designed to automate model preparation rather than replace certified hydraulic engineering software.

---

## 7. Frontend and Dashboard

### Streamlit

Used for:

* File upload
* Processing controls
* Interactive dashboard
* Results visualization

### Folium

Used for:

* Interactive maps
* GIS layer visualization
* Drainage network display

### Plotly

Used for:

* Elevation profiles
* Cross-section graphs
* Risk charts
* Hydraulic plots

---

## 8. Data Formats

### Raster

```text
GeoTIFF
.tif
.tiff
```

### Vector

```text
GeoJSON
Shapefile
```

### Tables

```text
CSV
JSON
```

### Reports

```text
HTML
PDF
```

---

## 9. Development Environment

```text
Operating System: Windows
Language: Python 3.12
Environment: Virtual Environment
IDE: Visual Studio Code
Version Control: Git
Repository: GitHub
```

---

## 10. Prototype Architecture

```text
Frontend
   ↓
Streamlit
   ↓
Python Processing Layer
   ↓
Geospatial Engine
   ↓
AI/ML Engine
   ↓
Hydrology Engine
   ↓
Optimization Engine
   ↓
Hydraulic Engine
   ↓
Reporting Engine
```
