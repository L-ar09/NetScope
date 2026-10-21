"""Load and summarize NetScope's structured application metrics."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from monitoring.logger import DEFAULT_METRICS_PATH


def load_metrics(path: Path = DEFAULT_METRICS_PATH) -> list[dict[str, str]]:
    """Return all metric rows, or an empty list when no test has run yet."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def _number(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "") or 0)
    except ValueError:
        return 0.0


def summarize(rows: list[dict[str, str]]) -> dict[str, float | int]:
    """Calculate application-level health and performance measures."""
    client_rows = [row for row in rows if row.get("actor") == "client"]
    total = len(client_rows)
    successful = sum(row.get("status") == "success" for row in client_rows)
    timeouts = sum(row.get("status") == "timeout" for row in client_rows)
    response_values = [_number(row, "response_ms") for row in client_rows if row.get("response_ms")]
    throughput_values = [_number(row, "throughput_mbps") for row in client_rows if row.get("throughput_mbps")]
    return {
        "total_requests": total,
        "successful_requests": successful,
        "failed_requests": total - successful,
        "timeout_requests": timeouts,
        "success_rate_percent": (successful / total * 100) if total else 0.0,
        "timeout_rate_percent": (timeouts / total * 100) if total else 0.0,
        "average_response_ms": (sum(response_values) / len(response_values)) if response_values else 0.0,
        "average_throughput_mbps": (sum(throughput_values) / len(throughput_values)) if throughput_values else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize NetScope application metrics.")
    parser.add_argument("--path", type=Path, default=DEFAULT_METRICS_PATH)
    args = parser.parse_args()
    print(json.dumps(summarize(load_metrics(args.path)), indent=2))


if __name__ == "__main__":
    main()
