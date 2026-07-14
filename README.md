# Industrial IoT Platform

**Industrial IoT data platform for sensor monitoring and analytics**

A scalable platform for ingesting, storing, visualizing and alerting on industrial sensor data — designed for biogas plants, manufacturing and energy operations.

---

## 🌐 Live Portfolio

📡 **Platform documentation and dashboard preview:** https://brunnobach.github.io/industrial-iot-platform/

---

## 🎯 What this project demonstrates

| Skill | How it is applied here |
|-------|------------------------|
| **Time-series data** | InfluxDB / TimescaleDB for sensor data |
| **IoT protocols** | MQTT broker for device ingestion |
| **Backend API** | FastAPI for data query and alerts |
| **Visualization** | Grafana dashboards |
| **Solutions architecture** | End-to-end system design |

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌─────────────────────┐
│   Sensors    │────▶│ MQTT Broker  │────▶│  Time-Series DB     │
│  (Simulated) │     │   (Mosquitto)│     │  (InfluxDB/Timescale)│
└──────────────┘     └──────────────┘     └──────────┬──────────┘
                                                       │
                                                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Query + Alert Service               │
└─────────────────────────────────────────────────────────────┘
                                                       │
                                                       ▼
                                             ┌─────────────────┐
                                             │ Grafana Dashboard │
└─────────────────┘
```

---

## 🛠️ Tech Stack

- Python 3.10+
- MQTT (Mosquitto)
- InfluxDB / TimescaleDB
- FastAPI
- Grafana
- Docker / Docker Compose

---

## 📁 Project Structure

```
industrial-iot-platform/
├── docker-compose.yml     # Full stack: MQTT, DB, API, Grafana
├── simulator/
│   └── sensor_simulator.py # Simulates industrial sensors
├── api/
│   └── main.py              # FastAPI query and alert endpoints
├── grafana/
│   └── dashboards/          # Pre-configured dashboards
├── docs/
│   └── architecture.md
├── tests/
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/Brunnobach/industrial-iot-platform.git
cd industrial-iot-platform

docker-compose up -d
```

Access:
- Grafana: http://localhost:3000
- FastAPI docs: http://localhost:8000/docs

---

## 📊 Dashboards

- Real-time sensor overview
- Temperature, pressure, pH and flow trends
- Alert history and threshold breaches

---

## 🤝 Connect

Built by [Brunno Bachmann](https://www.linkedin.com/in/brunno-bachmann-865429173) as part of a portfolio transition into industrial data systems and IoT.

---

## 📄 License

MIT
