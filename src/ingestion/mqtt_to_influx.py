"""Ingestion service that subscribes to sensor telemetry data on an MQTT broker
and writes batches of readings to InfluxDB.
"""

import json
import logging
import os
import time
from queue import Empty, Queue
from typing import Any, Dict, List

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# MQTT settings loaded from environment
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "factory/sensors/#")

# InfluxDB settings loaded from environment
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "iiot-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "iiot-org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "iiot-bucket")

# Batching and queuing configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "2.0"))

# Thread-safe queue for incoming MQTT messages
write_queue: Queue = Queue()

# Initialize connection client and write API for InfluxDB
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def on_connect(client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int, properties: Any = None) -> None:
    """Callback triggered upon connecting to the MQTT broker. Subscribes to the designated topic."""
    logger.info("Connected to MQTT broker with response code: %s", rc)
    client.subscribe(MQTT_TOPIC, qos=1)


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    """Callback triggered when a telemetry payload is received. Enqueues the decoded JSON data."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        logger.debug("Enqueued message from topic '%s': %s", msg.topic, payload)
        write_queue.put(payload)
    except json.JSONDecodeError as exc:
        logger.warning("Dropped invalid JSON payload on topic %s: %s", msg.topic, exc)
    except Exception as exc:
        logger.error("Error processing MQTT message: %s", exc)


def payload_to_point(payload: Dict[str, Any]) -> Point:
    """Transforms a raw telemetry dict payload into an InfluxDB Time-Series Point object.

    Args:
        payload: Dictionary containing 'measurement', 'sensor_id', 'value', 'unit', and optional 'timestamp'.

    Returns:
        Point: Formatted InfluxDB Point ready to be stored.
    """
    measurement = payload.get("measurement", "sensor")
    point = (
        Point(measurement)
        .tag("sensor_id", payload.get("sensor_id", "unknown"))
        .tag("unit", payload.get("unit", ""))
        .field("value", float(payload.get("value", 0.0)))
    )
    ts = payload.get("timestamp")
    if ts:
        point.time(int(ts * 1e9))  # Convert float timestamp in seconds to nanoseconds
    return point


def flush_batch(batch: List[Dict[str, Any]]) -> None:
    """Writes a accumulated batch of telemetry points to the InfluxDB bucket.

    Args:
        batch: Accumulation list of decoded MQTT message dicts.
    """
    if not batch:
        return
    try:
        points = [payload_to_point(p) for p in batch]
        write_api.write(bucket=INFLUX_BUCKET, record=points)
        logger.info("Successfully flushed batch of %d telemetry points to InfluxDB", len(points))
    except Exception as exc:
        logger.error("Failed writing batch to InfluxDB: %s", exc)


def main() -> None:
    """Main execution loop setting up the MQTT listener and handling batch flushes."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mqtt-to-influx")
    client.on_connect = on_connect
    client.on_message = on_message

    logger.info("Connecting to MQTT broker at %s:%d", MQTT_HOST, MQTT_PORT)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    batch = []
    last_flush = time.time()
    logger.info("Telemetry ingestion loop started")

    try:
        while True:
            try:
                # Polling the queue for new messages
                item = write_queue.get(timeout=0.5)
                batch.append(item)
            except Empty:
                pass

            # Flush batch if batch size limit reached or time interval elapsed
            if len(batch) >= BATCH_SIZE or (time.time() - last_flush) >= FLUSH_INTERVAL:
                flush_batch(batch)
                batch = []
                last_flush = time.time()
    except KeyboardInterrupt:
        logger.info("Termination signal received. Shutting down ingestion service.")
    finally:
        # Guarantee flushing remaining points and clean connection teardown
        flush_batch(batch)
        client.loop_stop()
        client.disconnect()
        influx_client.close()
        logger.info("Ingestion service stopped.")


if __name__ == "__main__":
    main()

