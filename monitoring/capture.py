"""Optional tshark automation for NetScope packet captures and CSV exports."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

PACKET_FIELDS = [
    "frame.number",
    "frame.time_relative",
    "_ws.col.Protocol",
    "ip.src",
    "ip.dst",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "tcp.flags.syn",
    "tcp.flags.ack",
    "tcp.analysis.retransmission",
    "tcp.analysis.ack_rtt",
    "frame.len",
    "tcp.len",
    "udp.length",
    "_ws.col.Info",
]


def tshark_path() -> str | None:
    """Return the tshark executable when Wireshark's command-line tool is installed."""
    on_path = shutil.which("tshark")
    if on_path:
        return on_path
    standard_install = Path("C:/Program Files/Wireshark/tshark.exe")
    return str(standard_install) if standard_install.is_file() else None


def require_tshark() -> str:
    path = tshark_path()
    if not path:
        raise RuntimeError(
            "tshark was not found. Install Wireshark with tshark and Npcap, or use the manual Wireshark workflow in README.md."
        )
    return path


def capture_command(interface: str, output: Path, capture_filter: str, duration: int) -> list[str]:
    """Build a bounded tshark capture command without starting it."""
    if duration < 1:
        raise ValueError("duration must be at least one second")
    return [
        require_tshark(), "-i", interface, "-f", capture_filter,
        "-a", f"duration:{duration}", "-w", str(output),
    ]


def export_command(capture: Path, output: Path, display_filter: str) -> list[str]:
    """Build a tshark command that exports fields consumed by packet_analyzer."""
    return [
        require_tshark(), "-r", str(capture), "-Y", display_filter,
        "-T", "fields", "-E", "header=y", "-E", "separator=,", "-E", "quote=d",
        *(part for field in PACKET_FIELDS for part in ("-e", field)),
    ]


def list_interfaces() -> int:
    """Print tshark's capture interfaces."""
    return subprocess.run([require_tshark(), "-D"], check=False).returncode


def capture(interface: str, output: Path, capture_filter: str, duration: int) -> int:
    """Capture a bounded packet trace, creating its destination directory if needed."""
    output.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(capture_command(interface, output, capture_filter, duration), check=False).returncode


def export(capture_file: Path, output: Path, display_filter: str) -> int:
    """Export selected packet fields to a CSV file."""
    if not capture_file.is_file():
        raise FileNotFoundError(f"Capture file not found: {capture_file}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as destination:
        return subprocess.run(export_command(capture_file, output, display_filter), stdout=destination, check=False).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture or export NetScope traffic with tshark.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list-interfaces", action="store_true")
    action.add_argument("--capture", type=Path, metavar="PCAPNG")
    action.add_argument("--export", type=Path, metavar="PCAPNG")
    parser.add_argument("--interface", help="tshark interface number or name; required for --capture")
    parser.add_argument("--output", type=Path, help="Output CSV; required for --export")
    parser.add_argument("--capture-filter", default="tcp port 5001", help="BPF capture filter")
    parser.add_argument("--display-filter", default="tcp.port == 5001", help="Wireshark display filter")
    parser.add_argument("--duration", type=int, default=15, help="Capture length in seconds")
    args = parser.parse_args()

    try:
        if args.list_interfaces:
            raise SystemExit(list_interfaces())
        if args.capture:
            if not args.interface:
                parser.error("--interface is required with --capture")
            raise SystemExit(capture(args.interface, args.capture, args.capture_filter, args.duration))
        if not args.output:
            parser.error("--output is required with --export")
        raise SystemExit(export(args.export, args.output, args.display_filter))
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
