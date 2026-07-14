import json
import logging
import os
import random
import time

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "factory/sensors")
INTERVAL = float(os.getenv("SIM_INTERVAL", "1.0"))

SENSORS = [
    {"id": "sensor_001", "type": "temperature", "unit": "celsius", "base": 75.0, "var": 5.0},
    {"id": "sensor_002", "type": "pressure", "unit": "bar", "base": 2.5, "var": 0.2},
    {"id": "sensor_003", "type": "ph", "unit": "pH", "base": 7.0, "var": 0.3},
    {"id": "sensor_004", "type": "flow", "unit": "m3/h", "base": 12.0, "var": 1.5},
    {"id": "sensor_005", "type": "vibration", "unit": "mm/s", "base": 3.0, "var": 0.8},
]


def build_payload(sensor):
    value = round(random.gauss(sensor["base"], sensor["var"]), 3)
    return {
        "sensor_id": sensor["id"],
        "measurement": sensor["type"],
        "value": value,
        "unit": sensor["unit"],
        "timestamp": time.time(),
    }


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sensor-simulator")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    logger.info("Sensor simulator connected to %s:%d", MQTT_HOST, MQTT_PORT)

    try:
        while True:
            for sensor in SENSORS:
                payload = build_payload(sensor)
                topic = f"{TOPIC_PREFIX}/{sensor['type']}/{sensor['id']}"
                client.publish(topic, json.dumps(payload), qos=1)
                logger.debug("Published to %s: %s", topic, payload)
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        logger.info("Shutting down simulator")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
