"""Run parallel TCP echo clients to demonstrate concurrent server handling."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from client.tcp_echo_client import DEFAULT_HOST, DEFAULT_PORT, echo


@dataclass(frozen=True)
class ConcurrentResult:
    client_id: int
    message: str
    response_ms: float
    success: bool
    error: str = ""


def run_concurrent_echoes(client_count: int, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> list[ConcurrentResult]:
    """Send one unique echo request from each client thread."""
    if client_count < 1:
        raise ValueError("client_count must be at least 1")

    def run_one(client_id: int) -> ConcurrentResult:
        message = f"NetScope concurrent client {client_id}"
        try:
            response, response_ms = echo(message, host, port)
            if response != message:
                return ConcurrentResult(client_id, message, response_ms, False, "Echo response mismatch")
            return ConcurrentResult(client_id, message, response_ms, True)
        except OSError as error:
            return ConcurrentResult(client_id, message, 0.0, False, str(error))

    results: list[ConcurrentResult] = []
    with ThreadPoolExecutor(max_workers=client_count) as executor:
        futures = [executor.submit(run_one, client_id) for client_id in range(1, client_count + 1)]
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda result: result.client_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run parallel NetScope TCP echo clients.")
    parser.add_argument("--clients", type=int, default=5, help="Number of parallel clients (default: 5)")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    results = run_concurrent_echoes(args.clients, args.host, args.port)
    for result in results:
        state = "SUCCESS" if result.success else f"FAILED: {result.error}"
        print(f"Client {result.client_id}: {state} ({result.response_ms:.2f} ms)")
    successful = sum(result.success for result in results)
    print(f"Completed: {successful}/{len(results)} successful")


if __name__ == "__main__":
    main()
