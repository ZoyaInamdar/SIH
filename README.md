# AI-Enabled Antarctic Navigation Decision Support System

An AI/physics-based navigation decision-support prototype for safer and more fuel-efficient Antarctic vessel navigation.

## Core capabilities

* Sea-ice forecasting
* Iceberg trajectory prediction
* Underwater iceberg-risk estimation
* Bathymetric grounding-risk assessment
* Safe route planning
* Fuel-aware route comparison
* Live ship position through NMEA
* AIS vessel awareness
* Confidence and data-freshness indicators
* Offline-first cached data support

## Architecture

Environmental Data
→ Hazard Intelligence
→ Prediction
→ Safety Analysis
→ Route Planning
→ Navigation Display

## Technology

### Backend

* Python
* FastAPI
* SQLite/SpatiaLite

### Frontend

* React
* MapLibre/Mapbox
* Deck.gl
* React Three Fiber

### Navigation

* NMEA 0183
* WebSocket
* A*
* RTZ/JSON route output

## Project Structure

```text
antartic_nav/
├── backend/
├── frontend/
├── data/
├── models/
├── scripts/
├── docs/
├── requirements.txt
├── .gitignore
└── README.md
```

## Important

This system is a navigation decision-support system.

It does not directly control the vessel's steering or autopilot.
