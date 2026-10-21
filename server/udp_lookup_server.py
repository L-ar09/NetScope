"""Educational UDP lookup server for NetScope; this is not real DNS."""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from monitoring.logger import MetricsLogger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5003
RECORDS_PATH = Path(__file__).resolve().parents[1] / "data" / "dns_records.json"


def load_records(path: Path = RECORDS_PATH) -> dict[str, str]:
    """Load and normalize the local, simulated name-to-address records."""
    with path.open(encoding="utf-8") as source:
        raw_records = json.load(source)
    return {str(name).lower(): str(address) for name, address in raw_records.items()}


class UDPLookupServer:
    """Stoppable UDP request/response server using static local records."""

    def __init__(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
        records: dict[str, str] | None = None, logger: MetricsLogger | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.records = records if records is not None else load_records()
        self._socket: socket.socket | None = None
        self._stopped = threading.Event()
        self.logger = logger

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self.port

    def serve_forever(self, ready: Callable[[tuple[str, int]], None] | None = None) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
            self._socket = server
            server.bind((self.host, self.port))
            self.host, self.port = server.getsockname()
            server.settimeout(0.2)
            if ready:
                ready(self.address)
            print(f"UDP Lookup Server running on {self.host}:{self.port}", flush=True)

            while not self._stopped.is_set():
                try:
                    data, peer = server.recvfrom(1024)
                except TimeoutError:
                    continue
                except OSError:
                    break
                domain = data.decode("utf-8", errors="replace").strip().lower()
                answer = self.records.get(domain, "NOT_FOUND")
                start = time.perf_counter()
                request_id = str(uuid.uuid4())
                try:
                    server.sendto(answer.encode("utf-8"), peer)
                    if self.logger:
                        self.logger.log(
                            request_id=request_id, actor="server", protocol="UDP", service="lookup",
                            status="success", response_ms=round((time.perf_counter() - start) * 1000, 3),
                            bytes_transferred=len(data), client_id="",
                        )
                except OSError as error:
                    if self.logger:
                        self.logger.log(
                            request_id=request_id, actor="server", protocol="UDP", service="lookup",
                            status="failed", response_ms=round((time.perf_counter() - start) * 1000, 3),
                            bytes_transferred=len(data), client_id="", error_type=type(error).__name__,
                        )
                    continue
                print(f"Lookup: {domain or '<empty>'} -> {answer}", flush=True)

    def shutdown(self) -> None:
        self._stopped.set()
        if self._socket is not None:
            self._socket.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NetScope UDP lookup server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    UDPLookupServer(args.host, args.port, logger=MetricsLogger()).serve_forever()


if __name__ == "__main__":
    main()
