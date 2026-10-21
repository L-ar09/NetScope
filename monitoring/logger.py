"""Thread-safe structured CSV logging for NetScope network operations."""

from __future__ import annotations

import csv
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_METRICS_PATH = Path(__file__).resolve().parents[1] / "data" / "metrics.csv"

FIELDS = [
    "timestamp",
    "request_id",
    "actor",
    "protocol",
    "service",
    "status",
    "response_ms",
    "bytes_transferred",
    "throughput_mbps",
    "client_id",
    "fault_type",
    "fault_enabled",
    "error_type",
]


class MetricsLogger:
    """Append consistently-shaped metric records without interleaving thread writes."""

    def __init__(self, path: Path = DEFAULT_METRICS_PATH) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def log(self, **record: Any) -> str:
        """Append one record and return its request identifier."""
        request_id = str(record.get("request_id") or uuid.uuid4())
        row = {field: "" for field in FIELDS}
        row.update(record)
        row["timestamp"] = datetime.now(UTC).isoformat()
        row["request_id"] = request_id
        row["fault_type"] = row.get("fault_type") or "none"
        row["fault_enabled"] = str(bool(row.get("fault_enabled", False))).lower()

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not self.path.exists() or self.path.stat().st_size == 0
            with self.path.open("a", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=FIELDS, extrasaction="ignore")
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
        return request_id
