"""A loopback TCP echo server used by the NetScope Day 1 exercises."""

from __future__ import annotations

import argparse
import socket
import threading
from collections.abc import Callable

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
BUFFER_SIZE = 4096


class TCPEchoServer:
    """Small stoppable TCP echo server suitable for local experiments and tests."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None
        self._stopped = threading.Event()

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

    @staticmethod
    def _handle_client(connection: socket.socket) -> None:
        with connection:
            while True:
                data = connection.recv(BUFFER_SIZE)
                if not data:
                    return
                connection.sendall(data)

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
    TCPEchoServer(args.host, args.port).serve_forever()


if __name__ == "__main__":
    main()
