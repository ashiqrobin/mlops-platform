import os
import time

import requests
from prometheus_client import Gauge, start_http_server

DAGSTER_HEALTH_URL = os.getenv(
    "DAGSTER_HEALTH_URL", "http://dagster:3000/server_info"
)
EXPORTER_PORT = int(os.getenv("DAGSTER_METRICS_PORT", "9200"))
POLL_INTERVAL_SECONDS = int(os.getenv("DAGSTER_POLL_SECONDS", "15"))

DAGSTER_HEALTH_GAUGE = Gauge(
    "dagster_webserver_up",
    "1 when the Dagster webserver health endpoint responds with HTTP 200",
)
DAGSTER_RESPONSE_MS = Gauge(
    "dagster_webserver_response_ms",
    "Response time of Dagster webserver health checks in milliseconds",
)


def check_health() -> None:
    start = time.perf_counter()
    status = 0
    try:
        resp = requests.get(DAGSTER_HEALTH_URL, timeout=5)
        status = 1 if resp.ok else 0
    except requests.RequestException:
        status = 0
    duration_ms = (time.perf_counter() - start) * 1000
    DAGSTER_HEALTH_GAUGE.set(status)
    DAGSTER_RESPONSE_MS.set(duration_ms)


def main() -> None:
    start_http_server(EXPORTER_PORT, addr="0.0.0.0")
    while True:
        check_health()
        time.sleep(max(5, POLL_INTERVAL_SECONDS))


if __name__ == "__main__":
    main()
