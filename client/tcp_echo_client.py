"""Client for the NetScope TCP echo service."""

from __future__ import annotations

import argparse
import socket
import time
import uuid

from monitoring.logger import MetricsLogger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001


def echo(
    message: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 5.0,
    logger: MetricsLogger | None = None,
    client_id: str = "tcp_echo_client",
) -> tuple[str, float]:
    """Echo *message* and return the echoed text with round-trip time in milliseconds."""
    payload = message.encode("utf-8")
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            client.sendall(payload)
            response = bytearray()
            while len(response) < len(payload):
                chunk = client.recv(len(payload) - len(response))
                if not chunk:
                    raise ConnectionError("TCP echo server closed the connection before replying")
                response.extend(chunk)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="TCP", service="echo",
                status="success", response_ms=round(elapsed_ms, 3),
                bytes_transferred=len(payload), client_id=client_id,
            )
        return response.decode("utf-8"), elapsed_ms
    except TimeoutError as error:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="TCP", service="echo",
                status="timeout", response_ms=round(elapsed_ms, 3),
                bytes_transferred=len(payload), client_id=client_id, error_type=type(error).__name__,
            )
        raise
    except OSError as error:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="TCP", service="echo",
                status="failed", response_ms=round(elapsed_ms, 3),
                bytes_transferred=len(payload), client_id=client_id, error_type=type(error).__name__,
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a message to the NetScope TCP echo server.")
    parser.add_argument("message", nargs="?", default="Hello NetScope!")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    response, elapsed_ms = echo(args.message, args.host, args.port, logger=MetricsLogger())
    print(f"Received: {response}")
    print(f"Response time: {elapsed_ms:.2f} ms")


if __name__ == "__main__":
    main()
