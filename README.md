# Industrial IoT Platform

A fully functional Industrial IoT data platform for sensor monitoring, analytics and alerting — designed for biogas plants, manufacturing and energy operations.

**Live portfolio:** https://brunnobach.github.io/industrial-iot-platform/

---

## What this project demonstrates

| Skill | How it is applied here |
|---|---|
| Time-series data | InfluxDB 2.x for sensor data storage |
| IoT protocols | MQTT broker with Mosquitto |
| Backend API | FastAPI for querying data and alerts |
| Visualization | Grafana dashboards with provisioning |
| DevOps / MLOps | Docker Compose, CI/CD with GitHub Actions |

---

## Architecture

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│ Sensor Simulator│────▶│ MQTT Broker │────▶│ Ingestion   │────▶│  InfluxDB    │
│   (Python)      │     │  (Mosquitto)│     │   Service   │     │  (Time-Series)│
└─────────────────┘     └─────────────┘     └─────────────┘     └──────┬───────┘
                                                                      │
                         ┌──────────────────────────────────────────┐
                         │          FastAPI Query Service           │
                         └────────────────────┬─────────────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │   Grafana   │
                                       │  Dashboard  │
                                       └─────────────┘
```

---

## Tech Stack

- Python 3.12
- FastAPI + Uvicorn
- Paho MQTT
- InfluxDB 2.7
- Mosquitto 2.0
- Grafana 10.4
- Docker / Docker Compose
- Pytest

---

## Project Structure

```
industrial-iot-platform/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
├── index.html              # GitHub Pages landing page
├── _config.yml             # Jekyll / GitHub Pages config
├── .github/workflows/ci.yml
├── src/
│   ├── simulator/
│   │   └── sensor_simulator.py
│   ├── ingestion/
│   │   └── mqtt_to_influx.py
│   └── api/
│       └── main.py
├── tests/
│   └── test_iiot.py
├── mosquitto/
│   └── config/mosquitto.conf
└── grafana/
    ├── provisioning/
    │   ├── datasources/influxdb.yml
    │   └── dashboards/dashboards.yml
    └── dashboards/
        └── industrial_iot_dashboard.json
```

---

## Quick Start

```bash
git clone https://github.com/Brunnobach/industrial-iot-platform.git
cd industrial-iot-platform

docker-compose up -d
```

Wait ~20 seconds for services to start, then open:

- **Grafana:** http://localhost:3000 (admin/admin)
- **FastAPI docs:** http://localhost:8000/docs
- **MQTT:** localhost:1883

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/sensors/last` | Latest sensor readings |
| GET | `/sensors/history` | Historical sensor data |
| POST | `/alerts/check` | Check alert thresholds |
| GET | `/measurements` | List available measurements |

### Example queries

```bash
# Latest readings
curl http://localhost:8000/sensors/last

# Temperature history for the last 10 minutes
curl "http://localhost:8000/sensors/history?measurement=temperature&minutes=10"

# Check temperature alert threshold
curl -X POST http://localhost:8000/alerts/check \
  -H "Content-Type: application/json" \
  -d '{"measurement": "temperature", "threshold": 80, "operator": "above"}'
```

---

## Dashboards

The pre-provisioned Grafana dashboard shows:

- Real-time temperature and pressure gauges
- Temperature and pressure trend charts
- Combined pH, flow and vibration time-series
- Auto-refresh every 5 seconds

---

## Running Tests

```bash
pip install -r requirements.txt
pytest
```

---

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):

- Runs unit tests on every push/PR
- Builds the Docker image
- Starts the full Docker Compose stack and verifies the API health
- Deploys the GitHub Pages landing page on `main` merges

---

## Connect

Built by [Brunno Bachmann](https://www.linkedin.com/in/brunno-bachmann-865429173) as part of a portfolio transition into industrial data systems and IoT.

---

## License

MIT
