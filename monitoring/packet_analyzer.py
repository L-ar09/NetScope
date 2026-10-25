"""Summarize packet observations exported from Wireshark or tshark."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_packet_observations(path: Path) -> list[dict[str, str]]:
    """Load a CSV export produced by :mod:`monitoring.capture`."""
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "set"}


def _number(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def _protocol(row: dict[str, str]) -> str:
    """Normalize protocol labels from either a test CSV or a tshark export."""
    label = (
        row.get("protocol")
        or row.get("_ws.col.Protocol")
        or row.get("_ws.col.protocol")
        or row.get("frame.protocols")
        or ""
    )
    label = label.upper()
    if "TCP" in label:
        return "TCP"
    if "UDP" in label:
        return "UDP"
    return label


def summarize_packets(rows: list[dict[str, str]]) -> dict[str, float | int]:
    """Return conservative counts derived from exported packet fields.

    A retransmission count represents only packets that Wireshark/tshark marked
    as retransmissions. It is not inferred from application timeouts.
    """
    tcp_rows = [row for row in rows if _protocol(row) == "TCP"]
    udp_rows = [row for row in rows if _protocol(row) == "UDP"]
    syn_packets = [row for row in tcp_rows if _truthy(row.get("tcp.flags.syn"))]
    syn_ack_packets = [
        row for row in syn_packets if _truthy(row.get("tcp.flags.ack"))
    ]
    ack_rtts = [_number(row.get("tcp.analysis.ack_rtt")) * 1000 for row in tcp_rows if row.get("tcp.analysis.ack_rtt")]
    return {
        "total_packets": len(rows),
        "tcp_packets": len(tcp_rows),
        "udp_packets": len(udp_rows),
        "tcp_syn_packets": len(syn_packets),
        "tcp_syn_ack_packets": len(syn_ack_packets),
        "suspected_tcp_retransmissions": sum(
            _truthy(row.get("tcp.analysis.retransmission")) for row in tcp_rows
        ),
        "average_tcp_ack_rtt_ms": (sum(ack_rtts) / len(ack_rtts)) if ack_rtts else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize NetScope packet observations exported to CSV.")
    parser.add_argument("input", type=Path, help="CSV exported with python -m monitoring.capture --export")
    args = parser.parse_args()
    print(json.dumps(summarize_packets(load_packet_observations(args.input)), indent=2))


if __name__ == "__main__":
    main()
