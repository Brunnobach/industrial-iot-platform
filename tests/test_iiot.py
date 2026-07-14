import json
import unittest
from unittest.mock import MagicMock, patch

from ingestion.mqtt_to_influx import payload_to_point
from simulator.sensor_simulator import build_payload


class SimulatorTests(unittest.TestCase):
    def test_build_payload(self):
        sensor = {"id": "s1", "type": "temperature", "unit": "celsius", "base": 50.0, "var": 1.0}
        payload = build_payload(sensor)
        self.assertEqual(payload["sensor_id"], "s1")
        self.assertEqual(payload["measurement"], "temperature")
        self.assertEqual(payload["unit"], "celsius")
        self.assertIsInstance(payload["value"], float)
        self.assertIn("timestamp", payload)


class IngestionTests(unittest.TestCase):
    def test_payload_to_point(self):
        payload = {
            "sensor_id": "s1",
            "measurement": "temperature",
            "value": 22.5,
            "unit": "celsius",
            "timestamp": 1700000000.0,
        }
        point = payload_to_point(payload)
        self.assertIn("s1", point.to_line_protocol())
        self.assertIn("temperature", point.to_line_protocol())


class APITests(unittest.TestCase):
    @patch("api.main.get_client")
    def test_list_measurements(self, mock_get_client):
        mock_q = MagicMock()
        mock_tables = MagicMock()
        mock_tables.__iter__.return_value = iter([])
        mock_q.query.return_value = mock_tables
        mock_get_client.return_value = (MagicMock(), mock_q)

        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)
        response = client.get("/measurements")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"measurements": []})


if __name__ == "__main__":
    unittest.main()
