import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi
from pydantic import BaseModel, Field

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration parameters loaded from environment variables
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "iiot-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "iiot-org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "iiot-bucket")

# Global InfluxDB connection state
_influx_client: Optional[InfluxDBClient] = None
_query_api: Optional[QueryApi] = None


def get_client() -> Tuple[InfluxDBClient, QueryApi]:
    """Retrieves or initializes the global InfluxDB client and query API.

    Returns:
        Tuple[InfluxDBClient, QueryApi]: The active InfluxDB client and its Query API instance.
    """
    global _influx_client, _query_api
    if _influx_client is None:
        logger.info("Initializing InfluxDBClient for URL: %s", INFLUX_URL)
        _influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        _query_api = _influx_client.query_api()
    return _influx_client, _query_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages the startup and shutdown lifecycles of the FastAPI application."""
    get_client()
    logger.info("FastAPI service connected to InfluxDB")
    yield
    global _influx_client
    if _influx_client:
        logger.info("Closing InfluxDB client connection")
        _influx_client.close()


app = FastAPI(
    title="Industrial IoT Platform API",
    description="Backend API for querying telemetry data, managing sensor history, and verifying alert rules.",
    version="1.0.0",
    lifespan=lifespan
)


class SensorReading(BaseModel):
    """Pydantic model representing a single sensor telemetry point."""
    sensor_id: str = Field(..., description="Unique identifier of the physical sensor")
    measurement: str = Field(..., description="The physical quantity being measured (e.g. temperature)")
    value: float = Field(..., description="Telemetry numeric value")
    unit: str = Field(..., description="Unit of measurement (e.g. celsius, bar)")
    timestamp: datetime = Field(..., description="Datetime timestamp of the reading in UTC")


class HealthStatus(BaseModel):
    """Pydantic model representing the system health status."""
    status: str = Field(..., description="General API operational status")
    influx: str = Field(..., description="Status of connection to InfluxDB")


class AlertRule(BaseModel):
    """Pydantic model defining threshold rules for alert checking."""
    measurement: str = Field(..., description="Telemetry metric name to analyze")
    threshold: float = Field(..., gt=0, description="Numeric threshold value to compare against")
    operator: str = Field("above", pattern="^(above|below)$", description="Comparison direction ('above' or 'below')")


@app.get("/health", response_model=HealthStatus, summary="Check API and database health status")
async def health() -> HealthStatus:
    """Verifies connection health to the InfluxDB database.

    Raises:
        HTTPException: If InfluxDB is unavailable or throws an error.
    """
    try:
        client, _ = get_client()
        client.health()
        return HealthStatus(status="ok", influx="connected")
    except Exception as exc:
        logger.error("Health check failure connecting to InfluxDB: %s", exc)
        raise HTTPException(status_code=503, detail="InfluxDB database unavailable") from exc


@app.get("/sensors/last", response_model=List[SensorReading], summary="Retrieve the latest sensor telemetry readings")
async def last_readings(
    measurement: Optional[str] = Query(None, description="Optional measurement type to filter by"),
    minutes: int = Query(5, ge=1, le=1440, description="Time window in minutes to search for the last point"),
) -> List[SensorReading]:
    """Queries InfluxDB for the most recent reading of each sensor matching the filters.

    Args:
        measurement: Optional filter for measurement type.
        minutes: The time window size to lookup the latest values.
    """
    _, q = get_client()
    start = f"-{minutes}m"
    measurement_filter = f'|> filter(fn: (r) => r._measurement == "{measurement}")' if measurement else ""
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


@app.get("/sensors/history", response_model=List[SensorReading], summary="Query historical telemetry values")
async def history(
    measurement: str = Query(..., description="Measurement type to retrieve historical data for"),
    minutes: int = Query(60, ge=1, le=10080, description="Historical range in minutes to query"),
) -> List[SensorReading]:
    """Fetches historical time-series telemetry data for a specific measurement type.

    Args:
        measurement: Target measurement metric (e.g. pressure).
        minutes: Time scope of history to fetch.
    """
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


@app.post("/alerts/check", summary="Check telemetry values against a threshold rule")
async def check_alerts(rule: AlertRule) -> Dict[str, Any]:
    """Computes the mean telemetry value over the last 5 minutes and flags threshold breaches.

    Args:
        rule: The alert threshold logic definition.
    """
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
            if (rule.operator == "above" and mean_value > rule.threshold) or \
               (rule.operator == "below" and mean_value < rule.threshold):
                alerts.append({
                    "sensor_id": record.values.get("sensor_id", "unknown"),
                    "measurement": rule.measurement,
                    "value": mean_value,
                    "threshold": rule.threshold,
                    "operator": rule.operator,
                    "status": "breach",
                })
    return {"alerts": alerts, "checked": True}


@app.get("/measurements", summary="List all active measurement metrics in the system")
async def list_measurements() -> Dict[str, List[str]]:
    """Retrieves unique names of telemetry measurements recorded within the last 1 hour."""
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

