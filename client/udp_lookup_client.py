"""Client for the NetScope UDP lookup simulation."""

from __future__ import annotations

import argparse
import socket
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5003


def lookup(domain: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0) -> tuple[str, float]:
    """Look up a simulated domain and return its answer plus response time in milliseconds."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(timeout)
        start = time.perf_counter()
        client.sendto(domain.strip().encode("utf-8"), (host, port))
        response, _ = client.recvfrom(1024)
    return response.decode("utf-8"), (time.perf_counter() - start) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the NetScope UDP lookup server.")
    parser.add_argument("domain", nargs="?", help="Name to resolve; prompts when omitted.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    domain = args.domain or input("Enter domain: ")
    try:
        answer, elapsed_ms = lookup(domain, args.host, args.port)
    except TimeoutError:
        print("Lookup timed out")
        return
    print(f"Resolved IP: {answer}")
    print(f"Response time: {elapsed_ms:.2f} ms")


if __name__ == "__main__":
    main()
