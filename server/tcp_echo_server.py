"""A loopback TCP echo server used by the NetScope Day 1 exercises."""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
import uuid
from collections.abc import Callable

from monitoring.logger import MetricsLogger
from server.fault_injector import FaultInjector

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
BUFFER_SIZE = 4096


def _decode_request(data: bytes) -> tuple[str, str, str, bool]:
    """Decode a NetScope envelope while retaining support for raw echo data."""
    try:
        payload = json.loads(data.decode("utf-8"))
        if isinstance(payload, dict) and payload.get("netscope") == "echo":
            return (
                str(payload.get("message", "")),
                str(payload.get("request_id") or uuid.uuid4()),
                str(payload.get("client_id", "")),
                True,
            )
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return data.decode("utf-8", errors="replace"), str(uuid.uuid4()), "", False


class TCPEchoServer:
    """Small stoppable TCP echo server suitable for local experiments and tests."""

    def __init__(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
        logger: MetricsLogger | None = None, fault_injector: FaultInjector | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._stopped = threading.Event()
        self.logger = logger
        self.fault_injector = fault_injector or FaultInjector()

    @property
    def address(self) -> tuple[str, int]:
        """The address currently assigned to the listening socket."""
        return self.host, self.port

    def serve_forever(self, ready: Callable[[tuple[str, int]], None] | None = None) -> None:
        """Accept connections and echo all bytes until :meth:`shutdown` is called."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            self._socket = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            self.host, self.port = server.getsockname()
            server.listen()
            server.settimeout(0.2)
            if ready:
                ready(self.address)
            print(f"TCP Echo Server running on {self.host}:{self.port}", flush=True)

            while not self._stopped.is_set():
                try:
                    connection, peer = server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    break
                print(f"Connected: {peer[0]}:{peer[1]}", flush=True)
                threading.Thread(
                    target=self._handle_client, args=(connection,), daemon=True
                ).start()

    def _handle_client(self, connection: socket.socket) -> None:
        with connection:
            while True:
                data = connection.recv(BUFFER_SIZE)
                if not data:
                    return
                start = time.perf_counter()
                message, request_id, client_id, structured = _decode_request(data)
                message_bytes = message.encode("utf-8")
                settings = self.fault_injector.settings()
                fault_type = self.fault_injector.fault_type(settings, "echo")
                try:
                    self.fault_injector.apply_delay(settings)
                    if settings.tcp_disconnect:
                        if self.logger:
                            self.logger.log(
                                request_id=request_id, actor="server", protocol="TCP", service="echo",
                                status="failed", response_ms=round((time.perf_counter() - start) * 1000, 3),
                                bytes_transferred=len(message_bytes), client_id=client_id, fault_type="tcp_disconnect",
                                fault_enabled=True, error_type="simulated_disconnect",
                            )
                        return
                    response = (
                        json.dumps({"netscope": "echo", "request_id": request_id, "message": message}).encode("utf-8") + b"\n"
                        if structured else data
                    )
                    connection.sendall(response)
                    if self.logger:
                        self.logger.log(
                            request_id=request_id, actor="server", protocol="TCP", service="echo",
                            status="success", response_ms=round((time.perf_counter() - start) * 1000, 3),
                            bytes_transferred=len(message_bytes), client_id=client_id, fault_type=fault_type,
                            fault_enabled=settings.enabled,
                        )
                except OSError as error:
                    if self.logger:
                        self.logger.log(
                            request_id=request_id, actor="server", protocol="TCP", service="echo",
                            status="failed", response_ms=round((time.perf_counter() - start) * 1000, 3),
                            bytes_transferred=len(message_bytes), client_id=client_id, error_type=type(error).__name__,
                            fault_type=fault_type, fault_enabled=settings.enabled,
                        )
                    return

    def shutdown(self) -> None:
        """Stop accepting connections without requiring a process signal."""
        self._stopped.set()
        if self._socket is not None:
            self._socket.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NetScope TCP echo server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    TCPEchoServer(args.host, args.port, logger=MetricsLogger()).serve_forever()


if __name__ == "__main__":
    main()
