"""Concurrent TCP file receiver for the NetScope Day 2 transfer experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import struct
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from monitoring.logger import MetricsLogger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5002
CHUNK_SIZE = 4096
MAX_METADATA_BYTES = 64 * 1024
MAX_FILE_BYTES = 100 * 1024 * 1024
DEFAULT_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive exactly *size* bytes or raise if the peer closes early."""
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(min(CHUNK_SIZE, size - len(data)))
        if not chunk:
            raise ConnectionError(f"Incomplete transfer: expected {size} bytes, received {len(data)}")
        data.extend(chunk)
    return bytes(data)


def file_hash(path: Path) -> str:
    """Return the SHA-256 digest of a file without reading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _send_json(sock: socket.socket, payload: dict[str, object]) -> None:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sock.sendall(struct.pack("!I", len(encoded)) + encoded)


def _receive_metadata(sock: socket.socket) -> dict[str, object]:
    metadata_length = struct.unpack("!I", recv_exact(sock, 4))[0]
    if not 0 < metadata_length <= MAX_METADATA_BYTES:
        raise ValueError("Invalid metadata length")
    metadata = json.loads(recv_exact(sock, metadata_length).decode("utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Metadata must be a JSON object")
    return metadata


class TCPFileServer:
    """Receive framed files and acknowledge their SHA-256 integrity result."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        upload_dir: Path = DEFAULT_UPLOAD_DIR,
        logger: MetricsLogger | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.upload_dir = Path(upload_dir)
        self._socket: socket.socket | None = None
        self._stopped = threading.Event()
        self.logger = logger

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self.port

    def serve_forever(self, ready: Callable[[tuple[str, int]], None] | None = None) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            self._socket = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            self.host, self.port = server.getsockname()
            server.listen()
            server.settimeout(0.2)
            if ready:
                ready(self.address)
            print(f"TCP File Server running on {self.host}:{self.port}", flush=True)
            while not self._stopped.is_set():
                try:
                    connection, peer = server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    break
                threading.Thread(
                    target=self._handle_client, args=(connection, peer), daemon=True
                ).start()

    def _destination_for(self, filename: str) -> Path:
        """Produce a safe, non-overwriting path inside the upload directory."""
        safe_name = Path(filename).name or "unnamed-upload"
        candidate = self.upload_dir / safe_name
        index = 1
        while candidate.exists():
            candidate = self.upload_dir / f"{Path(safe_name).stem}_{index}{Path(safe_name).suffix}"
            index += 1
        return candidate

    def _handle_client(self, connection: socket.socket, peer: tuple[str, int]) -> None:
        with connection:
            start = time.perf_counter()
            request_id = str(uuid.uuid4())
            file_size = 0
            try:
                metadata = _receive_metadata(connection)
                request_id = str(metadata.get("request_id") or request_id)
                filename = str(metadata.get("filename", ""))
                file_size = metadata.get("size")
                expected_hash = str(metadata.get("sha256", ""))
                if not isinstance(file_size, int) or not 0 <= file_size <= MAX_FILE_BYTES:
                    raise ValueError("Invalid file size")
                if len(expected_hash) != 64:
                    raise ValueError("Invalid SHA-256 digest")

                destination = self._destination_for(filename)
                digest = hashlib.sha256()
                remaining = file_size
                with destination.open("xb") as output:
                    while remaining:
                        chunk = recv_exact(connection, min(CHUNK_SIZE, remaining))
                        output.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)

                actual_hash = digest.hexdigest()
                integrity_ok = actual_hash == expected_hash
                _send_json(
                    connection,
                    {
                        "status": "success" if integrity_ok else "integrity_failed",
                        "filename": destination.name,
                        "bytes_received": file_size,
                        "sha256": actual_hash,
                    },
                )
                if self.logger:
                    elapsed_seconds = time.perf_counter() - start
                    self.logger.log(
                        request_id=request_id, actor="server", protocol="TCP", service="file_transfer",
                        status="success" if integrity_ok else "failed",
                        response_ms=round(elapsed_seconds * 1000, 3), bytes_transferred=file_size,
                        throughput_mbps=round((file_size * 8 / elapsed_seconds) / 1_000_000, 6) if elapsed_seconds else 0,
                        client_id="", error_type="" if integrity_ok else "integrity_failed",
                    )
                print(f"Received {destination.name} ({file_size} bytes) from {peer[0]}:{peer[1]}", flush=True)
            except (ConnectionError, OSError, ValueError, json.JSONDecodeError, struct.error) as error:
                if self.logger:
                    elapsed_seconds = time.perf_counter() - start
                    self.logger.log(
                        request_id=request_id, actor="server", protocol="TCP", service="file_transfer",
                        status="failed", response_ms=round(elapsed_seconds * 1000, 3),
                        bytes_transferred=file_size if isinstance(file_size, int) else 0,
                        client_id="", error_type=type(error).__name__,
                    )
                try:
                    _send_json(connection, {"status": "error", "error": str(error)})
                except OSError:
                    pass

    def shutdown(self) -> None:
        self._stopped.set()
        if self._socket is not None:
            self._socket.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NetScope TCP file server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--upload-dir", type=Path, default=DEFAULT_UPLOAD_DIR)
    args = parser.parse_args()
    TCPFileServer(args.host, args.port, args.upload_dir, logger=MetricsLogger()).serve_forever()


if __name__ == "__main__":
    main()
