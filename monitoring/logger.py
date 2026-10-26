"""Thread-safe structured CSV logging for NetScope network operations."""

from __future__ import annotations

import csv
import os
import threading
import time
import uuid
from contextlib import contextmanager
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

_PROCESS_LOCK = threading.RLock()
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 30.0


@contextmanager
def _exclusive_file_lock(path: Path):
    """Serialize appends across threads and separate local Python processes."""
    lock_path = path.with_name(f".{path.name}.lock")
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    with _PROCESS_LOCK:
        while True:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(descriptor)
                break
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime > STALE_LOCK_SECONDS:
                        lock_path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting to write metrics: {path}")
                time.sleep(0.01)
        try:
            yield
        finally:
            lock_path.unlink(missing_ok=True)


def _repair_csv_if_needed(path: Path) -> None:
    """Remove duplicate headers and incomplete rows left by older log versions."""
    if not path.exists() or path.stat().st_size == 0:
        return
    with path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.reader(source))
    valid_rows = [row for row in rows[1:] if row != FIELDS and len(row) == len(FIELDS)]
    if rows and rows[0] == FIELDS and len(valid_rows) == len(rows) - 1:
        return

    repair_path = path.with_name(f".{path.name}.repair")
    with repair_path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.writer(destination)
        writer.writerow(FIELDS)
        writer.writerows(valid_rows)
    repair_path.replace(path)


class MetricsLogger:
    """Append consistently-shaped metric records without interleaving thread writes."""

    def __init__(self, path: Path = DEFAULT_METRICS_PATH) -> None:
        self.path = Path(path)

    def log(self, **record: Any) -> str:
        """Append one record and return its request identifier."""
        request_id = str(record.get("request_id") or uuid.uuid4())
        row = {field: "" for field in FIELDS}
        row.update(record)
        row["timestamp"] = datetime.now(UTC).isoformat()
        row["request_id"] = request_id
        row["fault_type"] = row.get("fault_type") or "none"
        row["fault_enabled"] = str(bool(row.get("fault_enabled", False))).lower()

        with _exclusive_file_lock(self.path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _repair_csv_if_needed(self.path)
            write_header = not self.path.exists() or self.path.stat().st_size == 0
            with self.path.open("a", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=FIELDS, extrasaction="ignore")
                if write_header:
                    writer.writeheader()
                writer.writerow(row)
        return request_id
