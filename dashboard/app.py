"""Interactive local dashboard for NetScope measurements and experiments.

Run from the project root with ``python -m streamlit run dashboard/app.py``.
The dashboard reads local CSV/capture files only; it does not make network
requests or start/stop the NetScope services.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from monitoring.diagnosis import diagnose
from monitoring.metrics import load_metrics, summarize
from monitoring.packet_analyzer import load_packet_observations, summarize_packets


PROJECT_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = PROJECT_ROOT / "data" / "metrics.csv"
FAULT_CONFIG_PATH = PROJECT_ROOT / "data" / "fault_config.json"
CAPTURES_PATH = PROJECT_ROOT / "data" / "captures"

DEFAULT_FAULTS = {
    "delay_ms": 0,
    "udp_drop_probability": 0.0,
    "wrong_lookup": False,
    "tcp_disconnect": False,
}


def load_fault_settings(path: Path = FAULT_CONFIG_PATH) -> dict[str, int | float | bool]:
    """Read valid dashboard fault settings, falling back to safe defaults."""
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        saved = {}
    settings = DEFAULT_FAULTS | {key: saved[key] for key in DEFAULT_FAULTS if key in saved}
    try:
        settings["delay_ms"] = max(0, min(60_000, int(settings["delay_ms"])))
        settings["udp_drop_probability"] = max(0.0, min(1.0, float(settings["udp_drop_probability"])))
    except (TypeError, ValueError):
        return DEFAULT_FAULTS.copy()
    settings["wrong_lookup"] = bool(settings["wrong_lookup"])
    settings["tcp_disconnect"] = bool(settings["tcp_disconnect"])
    return settings


def save_fault_settings(settings: dict[str, int | float | bool], path: Path = FAULT_CONFIG_PATH) -> None:
    """Persist dashboard controls in the configuration read by the servers."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def metrics_dataframe(rows: list[dict[str, str]]) -> pd.DataFrame:
    """Convert metric rows to a display-friendly data frame."""
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    for column in ("response_ms", "bytes_transferred", "throughput_mbps"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return frame


def main() -> None:
    st.set_page_config(page_title="NetScope Dashboard", page_icon="📡", layout="wide")
    st.title("NetScope Dashboard")
    st.caption("Local application metrics, packet-capture summaries, and controlled fault experiments.")

    with st.sidebar:
        st.header("Navigation")
        st.caption("Refresh the page after running clients or exporting a packet capture.")
        if st.button("Refresh data"):
            st.rerun()

    rows = load_metrics(METRICS_PATH)
    summary = summarize(rows)
    frame = metrics_dataframe(rows)

    st.header("Application health")
    first, second, third, fourth = st.columns(4)
    first.metric("Client requests", summary["total_requests"])
    second.metric("Success rate", f'{summary["success_rate_percent"]:.1f}%')
    third.metric("Average response", f'{summary["average_response_ms"]:.2f} ms')
    fourth.metric("Timeouts", summary["timeout_requests"])

    if frame.empty:
        st.info("No metrics have been recorded yet. Start a NetScope server, run a client, then refresh this page.")
    else:
        st.subheader("Request metrics")
        client_frame = frame[frame["actor"] == "client"].copy()
        services = sorted(client_frame["service"].dropna().unique().tolist())
        statuses = sorted(client_frame["status"].dropna().unique().tolist())

        st.caption("Services")
        service_columns = st.columns([1] * len(services) + [5])
        selected_services = [
            service
            for column, service in zip(service_columns, services)
            if column.checkbox(service.replace("_", " ").title(), value=True, key=f"service_{service}")
        ]

        st.caption("Statuses")
        status_columns = st.columns([1] * len(statuses) + [5])
        selected_statuses = [
            status
            for column, status in zip(status_columns, statuses)
            if column.checkbox(status.title(), value=True, key=f"status_{status}")
        ]
        filtered = client_frame[
            client_frame["service"].isin(selected_services) & client_frame["status"].isin(selected_statuses)
        ]

        left, right = st.columns(2)
        with left:
            if not filtered.empty:
                st.plotly_chart(
                    px.line(filtered, x="timestamp", y="response_ms", color="service", markers=True,
                            title="Application response time"),
                    use_container_width=True,
                )
        with right:
            transfer_rows = filtered[filtered["throughput_mbps"] > 0]
            if not transfer_rows.empty:
                st.plotly_chart(
                    px.bar(transfer_rows, x="timestamp", y="throughput_mbps", color="service",
                           title="Transfer throughput"),
                    use_container_width=True,
                )
            else:
                st.info("Throughput appears after a successful file transfer.")
        st.dataframe(filtered.sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)

    st.header("Rule-based diagnostics")
    findings = diagnose(rows)
    if findings:
        st.dataframe(pd.DataFrame(findings), use_container_width=True, hide_index=True)
    else:
        st.success("No diagnostic findings in the recorded metrics.")

    st.header("Packet capture summary")
    capture_files = sorted(CAPTURES_PATH.glob("*.csv"))
    if not capture_files:
        st.info("No exported packet CSV files found in data/captures. Export a .pcapng file with monitoring.capture first.")
    else:
        selected_capture = st.selectbox("Exported capture CSV", capture_files, format_func=lambda item: item.name)
        try:
            packet_summary = summarize_packets(load_packet_observations(selected_capture))
            columns = st.columns(len(packet_summary))
            for column, (label, value) in zip(columns, packet_summary.items()):
                column.metric(label.replace("_", " ").title(), f"{value:.2f}" if isinstance(value, float) else value)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            st.error(f"Could not read {selected_capture.name}: {error}")

    st.header("Fault controls")
    st.warning("These controls modify data/fault_config.json. They affect the next request handled by a running NetScope server.")
    faults = load_fault_settings()
    with st.form("fault-controls"):
        delay = st.number_input("Server delay (ms)", min_value=0, max_value=60_000, value=int(faults["delay_ms"]), step=50)
        drop = st.slider("UDP response drop probability", 0.0, 1.0, float(faults["udp_drop_probability"]), 0.05)
        wrong_lookup = st.checkbox("Return a wrong UDP lookup address", value=bool(faults["wrong_lookup"]))
        tcp_disconnect = st.checkbox("Disconnect TCP before normal response", value=bool(faults["tcp_disconnect"]))
        save = st.form_submit_button("Save fault configuration")
    if save:
        save_fault_settings({
            "delay_ms": delay,
            "udp_drop_probability": drop,
            "wrong_lookup": wrong_lookup,
            "tcp_disconnect": tcp_disconnect,
        })
        st.success("Fault configuration saved. Run a client request, then refresh the dashboard.")


if __name__ == "__main__":
    main()
