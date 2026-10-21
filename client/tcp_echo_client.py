"""Client for the NetScope TCP echo service."""

from __future__ import annotations

import argparse
import socket
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001


def echo(message: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 5.0) -> tuple[str, float]:
    """Echo *message* and return the echoed text with round-trip time in milliseconds."""
    payload = message.encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as client:
        start = time.perf_counter()
        client.sendall(payload)
        response = bytearray()
        while len(response) < len(payload):
            chunk = client.recv(len(payload) - len(response))
            if not chunk:
                raise ConnectionError("TCP echo server closed the connection before replying")
            response.extend(chunk)
    return response.decode("utf-8"), (time.perf_counter() - start) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a message to the NetScope TCP echo server.")
    parser.add_argument("message", nargs="?", default="Hello NetScope!")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    response, elapsed_ms = echo(args.message, args.host, args.port)
    print(f"Received: {response}")
    print(f"Response time: {elapsed_ms:.2f} ms")


if __name__ == "__main__":
    main()
