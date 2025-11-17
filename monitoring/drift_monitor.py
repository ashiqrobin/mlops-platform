import csv
import hashlib
import os
import time
from typing import Optional

from prometheus_client import Gauge, start_http_server

DRIFT_DATA_PATH = os.getenv("DRIFT_DATA_PATH", "/opt/drift/data/sample_data.csv")
BASELINE_DATA_HASH = os.getenv("BASELINE_DATA_HASH", "")
DRIFT_MONITOR_INTERVAL_SECONDS = int(os.getenv("DRIFT_MONITOR_INTERVAL_SECONDS", "60"))
DRIFT_MONITOR_PORT = int(os.getenv("DRIFT_MONITOR_PORT", "9100"))

DRIFT_GAUGE = Gauge(
    "synthetic_data_drift_detected",
    "1 when dataset hash differs from the baseline, 0 otherwise",
)
ROW_COUNT_GAUGE = Gauge(
    "synthetic_data_row_count",
    "Row count observed in the latest drift evaluation",
)
LAST_CHECK_TS_GAUGE = Gauge(
    "synthetic_data_last_check_timestamp",
    "Unix timestamp of the last successful drift evaluation",
)


def compute_dataset_hash_and_rows() -> tuple[Optional[str], Optional[int]]:
    if not os.path.exists(DRIFT_DATA_PATH):
        return None, None

    with open(DRIFT_DATA_PATH, "rb") as f:
        data = f.read()
    dataset_hash = hashlib.sha256(data).hexdigest()

    with open(DRIFT_DATA_PATH, newline="") as f:
        reader = csv.reader(f)
        rows = sum(1 for row in reader if row)

    return dataset_hash, rows


def run_monitor() -> None:
    start_http_server(DRIFT_MONITOR_PORT, addr="0.0.0.0")
    while True:
        dataset_hash, rows = compute_dataset_hash_and_rows()
        if dataset_hash is None:
            DRIFT_GAUGE.set(1)
        else:
            drift_detected = 0 if not BASELINE_DATA_HASH else int(dataset_hash != BASELINE_DATA_HASH)
            DRIFT_GAUGE.set(drift_detected)
            if rows is not None:
                ROW_COUNT_GAUGE.set(rows)
            LAST_CHECK_TS_GAUGE.set(time.time())
        time.sleep(max(5, DRIFT_MONITOR_INTERVAL_SECONDS))


if __name__ == "__main__":
    run_monitor()
