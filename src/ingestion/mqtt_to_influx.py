import json
import logging
import os
import time
from queue import Queue, Empty

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "factory/sensors/#")

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "iiot-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "iiot-org")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "iiot-bucket")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
FLUSH_INTERVAL = float(os.getenv("FLUSH_INTERVAL", "2.0"))

write_queue: Queue = Queue()

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)


def on_connect(client, userdata, flags, rc, properties=None):
    logger.info("Connected to MQTT broker with code %s", rc)
    client.subscribe(MQTT_TOPIC, qos=1)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        logger.debug("Received on %s: %s", msg.topic, payload)
        write_queue.put(payload)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to decode message: %s", exc)
    except Exception as exc:
        logger.error("Error handling message: %s", exc)


def payload_to_point(payload):
    measurement = payload.get("measurement", "sensor")
    point = (
        Point(measurement)
        .tag("sensor_id", payload.get("sensor_id", "unknown"))
        .tag("unit", payload.get("unit", ""))
        .field("value", float(payload.get("value", 0.0)))
    )
    ts = payload.get("timestamp")
    if ts:
        point.time(int(ts * 1e9))
    return point


def flush_batch(batch):
    if not batch:
        return
    try:
        points = [payload_to_point(p) for p in batch]
        write_api.write(bucket=INFLUX_BUCKET, record=points)
        logger.info("Wrote %d points to InfluxDB", len(points))
    except Exception as exc:
        logger.error("Failed to write to InfluxDB: %s", exc)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mqtt-to-influx")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    batch = []
    last_flush = time.time()
    logger.info("Ingestion service started")

    try:
        while True:
            try:
                item = write_queue.get(timeout=0.5)
                batch.append(item)
            except Empty:
                pass

            if len(batch) >= BATCH_SIZE or (time.time() - last_flush) >= FLUSH_INTERVAL:
                flush_batch(batch)
                batch = []
                last_flush = time.time()
    except KeyboardInterrupt:
        logger.info("Shutting down ingestion service")
    finally:
        flush_batch(batch)
        client.loop_stop()
        client.disconnect()
        influx_client.close()


if __name__ == "__main__":
    main()
