from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from influxdb_client import InfluxDBClient
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "iiot-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "iiot-org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "iiot-bucket")

influx_client: Optional[InfluxDBClient] = None
query_api = None


def get_client():
    global influx_client, query_api
    if influx_client is None:
        influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = influx_client.query_api()
    return influx_client, query_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_client()
    logger.info("FastAPI service connected to InfluxDB")
    yield
    if influx_client:
        influx_client.close()


app = FastAPI(title="Industrial IoT Platform API", lifespan=lifespan)


class SensorReading(BaseModel):
    sensor_id: str
    measurement: str
    value: float
    unit: str
    timestamp: datetime


class HealthStatus(BaseModel):
    status: str
    influx: str


class AlertRule(BaseModel):
    measurement: str
    threshold: float = Field(..., gt=0)
    operator: str = Field("above", pattern="^(above|below)$")


@app.get("/health", response_model=HealthStatus)
async def health():
    try:
        client, _ = get_client()
        client.health()
        return HealthStatus(status="ok", influx="connected")
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        raise HTTPException(status_code=503, detail="InfluxDB unavailable") from exc


@app.get("/sensors/last", response_model=List[SensorReading])
async def last_readings(
    measurement: Optional[str] = Query(None, description="Filter by measurement type"),
    minutes: int = Query(5, ge=1, le=1440),
):
    _, q = get_client()
    start = f"-{minutes}m"
    measurement_filter = f"|> filter(fn: (r) => r._measurement == \"{measurement}\")" if measurement else ""
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: {start})
        |> filter(fn: (r) => r._field == "value")
        {measurement_filter}
        |> last()
    '''
    tables = q.query(flux)
    readings = []
    for table in tables:
        for record in table.records:
            readings.append(
                SensorReading(
                    sensor_id=record.values.get("sensor_id", "unknown"),
                    measurement=record.get_measurement(),
                    value=record.get_value(),
                    unit=record.values.get("unit", ""),
                    timestamp=record.get_time().replace(tzinfo=timezone.utc),
                )
            )
    return readings


@app.get("/sensors/history", response_model=List[SensorReading])
async def history(
    measurement: str = Query(..., description="Measurement type to query"),
    minutes: int = Query(60, ge=1, le=10080),
):
    _, q = get_client()
    start = f"-{minutes}m"
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: {start})
        |> filter(fn: (r) => r._measurement == "{measurement}")
        |> filter(fn: (r) => r._field == "value")
    '''
    tables = q.query(flux)
    readings = []
    for table in tables:
        for record in table.records:
            readings.append(
                SensorReading(
                    sensor_id=record.values.get("sensor_id", "unknown"),
                    measurement=record.get_measurement(),
                    value=record.get_value(),
                    unit=record.values.get("unit", ""),
                    timestamp=record.get_time().replace(tzinfo=timezone.utc),
                )
            )
    return readings


@app.post("/alerts/check")
async def check_alerts(rule: AlertRule):
    _, q = get_client()
    start = "-5m"
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: {start})
        |> filter(fn: (r) => r._measurement == "{rule.measurement}")
        |> filter(fn: (r) => r._field == "value")
        |> mean(column: "_value")
    '''
    tables = q.query(flux)
    alerts = []
    for table in tables:
        for record in table.records:
            mean_value = record.get_value()
            if rule.operator == "above" and mean_value > rule.threshold:
                alerts.append({
                    "sensor_id": record.values.get("sensor_id", "unknown"),
                    "measurement": rule.measurement,
                    "value": mean_value,
                    "threshold": rule.threshold,
                    "operator": rule.operator,
                    "status": "breach",
                })
            elif rule.operator == "below" and mean_value < rule.threshold:
                alerts.append({
                    "sensor_id": record.values.get("sensor_id", "unknown"),
                    "measurement": rule.measurement,
                    "value": mean_value,
                    "threshold": rule.threshold,
                    "operator": rule.operator,
                    "status": "breach",
                })
    return {"alerts": alerts, "checked": True}


@app.get("/measurements")
async def list_measurements():
    _, q = get_client()
    flux = f'''
    from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -1h)
        |> filter(fn: (r) => r._field == "value")
        |> group(columns: ["_measurement"])
        |> distinct(column: "_measurement")
    '''
    tables = q.query(flux)
    measurements = []
    for table in tables:
        for record in table.records:
            measurements.append(record.get_value())
    return {"measurements": measurements}
