"""Client for the NetScope UDP lookup simulation."""

from __future__ import annotations

import argparse
import socket
import time
import uuid

from monitoring.logger import MetricsLogger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5003


def lookup(
    domain: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 2.0,
    logger: MetricsLogger | None = None,
    client_id: str = "udp_lookup_client",
) -> tuple[str, float]:
    """Look up a simulated domain and return its answer plus response time in milliseconds."""
    payload = domain.strip().encode("utf-8")
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(timeout)
            client.sendto(payload, (host, port))
            response, _ = client.recvfrom(1024)
        elapsed_ms = (time.perf_counter() - start) * 1000
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="UDP", service="lookup",
                status="success", response_ms=round(elapsed_ms, 3),
                bytes_transferred=len(payload), client_id=client_id,
            )
        return response.decode("utf-8"), elapsed_ms
    except TimeoutError as error:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="UDP", service="lookup",
                status="timeout", response_ms=round(elapsed_ms, 3),
                bytes_transferred=len(payload), client_id=client_id, error_type=type(error).__name__,
            )
        raise
    except OSError as error:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="UDP", service="lookup",
                status="failed", response_ms=round(elapsed_ms, 3),
                bytes_transferred=len(payload), client_id=client_id, error_type=type(error).__name__,
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the NetScope UDP lookup server.")
    parser.add_argument("domain", nargs="?", help="Name to resolve; prompts when omitted.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    domain = args.domain or input("Enter domain: ")
    try:
        answer, elapsed_ms = lookup(domain, args.host, args.port, logger=MetricsLogger())
    except TimeoutError:
        print("Lookup timed out")
        return
    print(f"Resolved IP: {answer}")
    print(f"Response time: {elapsed_ms:.2f} ms")


if __name__ == "__main__":
    main()
