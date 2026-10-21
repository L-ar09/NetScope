"""Send a file to the NetScope TCP file server with framing and hash verification."""

from __future__ import annotations

import argparse
import json
import socket
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from server.tcp_file_server import CHUNK_SIZE, DEFAULT_HOST, DEFAULT_PORT, file_hash, recv_exact
from monitoring.logger import MetricsLogger


@dataclass(frozen=True)
class TransferResult:
    """Measured result of one TCP file-transfer request."""

    status: str
    received_filename: str
    bytes_transferred: int
    elapsed_seconds: float
    throughput_mbps: float
    sha256: str


def _receive_json(sock: socket.socket) -> dict[str, object]:
    length = struct.unpack("!I", recv_exact(sock, 4))[0]
    if not 0 < length <= 64 * 1024:
        raise ValueError("Invalid acknowledgement length")
    result = json.loads(recv_exact(sock, length).decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Invalid acknowledgement")
    return result


def transfer_file(
    path: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 10.0,
    logger: MetricsLogger | None = None,
    client_id: str = "tcp_file_client",
) -> TransferResult:
    """Transfer *path* and return the server acknowledgement plus performance data."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    size = path.stat().st_size
    digest = file_hash(path)
    request_id = str(uuid.uuid4())
    metadata = json.dumps(
        {"request_id": request_id, "filename": path.name, "size": size, "sha256": digest}
    ).encode("utf-8")

    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            client.sendall(struct.pack("!I", len(metadata)) + metadata)
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
                    client.sendall(chunk)
            acknowledgement = _receive_json(client)
        elapsed_seconds = time.perf_counter() - start

        status = str(acknowledgement.get("status", "error"))
        if status != "success":
            raise ConnectionError(str(acknowledgement.get("error", "Server rejected transfer")))
        server_hash = str(acknowledgement.get("sha256", ""))
        if server_hash != digest:
            raise ConnectionError("Server acknowledgement hash does not match the source file")
        throughput_mbps = (size * 8 / elapsed_seconds) / 1_000_000 if elapsed_seconds else 0.0
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="TCP", service="file_transfer",
                status="success", response_ms=round(elapsed_seconds * 1000, 3),
                bytes_transferred=size, throughput_mbps=round(throughput_mbps, 6), client_id=client_id,
            )
        return TransferResult(
            status=status,
            received_filename=str(acknowledgement.get("filename", "")),
            bytes_transferred=size,
            elapsed_seconds=elapsed_seconds,
            throughput_mbps=throughput_mbps,
            sha256=digest,
        )
    except TimeoutError as error:
        elapsed_seconds = time.perf_counter() - start
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="TCP", service="file_transfer",
                status="timeout", response_ms=round(elapsed_seconds * 1000, 3),
                bytes_transferred=size, client_id=client_id, error_type=type(error).__name__,
            )
        raise
    except OSError as error:
        elapsed_seconds = time.perf_counter() - start
        if logger:
            logger.log(
                request_id=request_id, actor="client", protocol="TCP", service="file_transfer",
                status="failed", response_ms=round(elapsed_seconds * 1000, 3),
                bytes_transferred=size, client_id=client_id, error_type=type(error).__name__,
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Transfer a file to the NetScope TCP file server.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    result = transfer_file(args.path, args.host, args.port, logger=MetricsLogger())
    print(f"Status: {result.status}")
    print(f"Received file: {result.received_filename}")
    print(f"Bytes transferred: {result.bytes_transferred}")
    print(f"SHA-256 verified: {result.sha256}")
    print(f"Duration: {result.elapsed_seconds:.4f} seconds")
    print(f"Throughput: {result.throughput_mbps:.2f} Mbps")


if __name__ == "__main__":
    main()
