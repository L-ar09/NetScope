"""Rule-based diagnosis based on NetScope application logs and configured faults."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from monitoring.logger import DEFAULT_METRICS_PATH
from monitoring.metrics import load_metrics


def diagnose(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return evidence-based diagnoses without overstating packet-level causes."""
    findings: list[dict[str, str]] = []
    for row in rows:
        fault = row.get("fault_type", "none")
        service = row.get("service", "unknown")
        if row.get("actor") == "server" and fault == "udp_response_drop":
            findings.append({
                "service": service,
                "observation": "Server received a UDP request and intentionally sent no response.",
                "probable_cause": "Configured simulated UDP response drop.",
                "recommendation": "Retry the request or reduce udp_drop_probability.",
                "evidence": "server fault log",
            })
        elif row.get("actor") == "server" and fault == "wrong_lookup":
            findings.append({
                "service": service,
                "observation": "Lookup response was generated while wrong_lookup was enabled.",
                "probable_cause": "Configured incorrect lookup mapping.",
                "recommendation": "Disable wrong_lookup or correct the lookup records.",
                "evidence": "server fault log",
            })
        elif row.get("actor") == "server" and fault == "tcp_disconnect":
            findings.append({
                "service": service,
                "observation": "TCP connection was closed by the server before a normal response.",
                "probable_cause": "Configured TCP disconnect.",
                "recommendation": "Retry the operation or disable tcp_disconnect.",
                "evidence": "server fault log",
            })
        elif row.get("actor") == "server" and fault == "artificial_delay":
            findings.append({
                "service": service,
                "observation": "Response processing included a configured delay.",
                "probable_cause": "Artificial application-level server delay.",
                "recommendation": "Reduce delay_ms or investigate server processing work.",
                "evidence": "server fault log",
            })
        elif row.get("actor") == "client" and row.get("status") == "timeout":
            findings.append({
                "service": service,
                "observation": "Client did not receive a response before its timeout.",
                "probable_cause": "Application timeout; packet loss is not proven without capture evidence.",
                "recommendation": "Check server fault logs and inspect the matching packet capture.",
                "evidence": "client timeout log",
            })
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose NetScope observations from metrics logs.")
    parser.add_argument("--path", type=Path, default=DEFAULT_METRICS_PATH)
    args = parser.parse_args()
    print(json.dumps(diagnose(load_metrics(args.path)), indent=2))


if __name__ == "__main__":
    main()
