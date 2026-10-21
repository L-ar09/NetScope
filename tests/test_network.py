"""Day 1 end-to-end tests against real loopback sockets."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from client.concurrent_test import run_concurrent_echoes
from client.tcp_file_client import transfer_file
from client.tcp_echo_client import echo
from client.udp_lookup_client import lookup
from monitoring.logger import MetricsLogger
from monitoring.metrics import load_metrics, summarize
from server.tcp_echo_server import TCPEchoServer
from server.tcp_file_server import TCPFileServer, file_hash
from server.udp_lookup_server import UDPLookupServer


@pytest.fixture
def tcp_server() -> TCPEchoServer:
    server = TCPEchoServer(port=0)
    ready = threading.Event()
    thread = threading.Thread(target=server.serve_forever, args=(lambda _: ready.set(),), daemon=True)
    thread.start()
    assert ready.wait(2), "TCP server did not start"
    yield server
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture
def udp_server() -> UDPLookupServer:
    server = UDPLookupServer(port=0)
    ready = threading.Event()
    thread = threading.Thread(target=server.serve_forever, args=(lambda _: ready.set(),), daemon=True)
    thread.start()
    assert ready.wait(2), "UDP server did not start"
    yield server
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture
def file_server(tmp_path: Path) -> TCPFileServer:
    server = TCPFileServer(port=0, upload_dir=tmp_path / "uploads")
    ready = threading.Event()
    thread = threading.Thread(target=server.serve_forever, args=(lambda _: ready.set(),), daemon=True)
    thread.start()
    assert ready.wait(2), "File server did not start"
    yield server
    server.shutdown()
    thread.join(timeout=2)


def test_tcp_echo_returns_exact_message(tcp_server: TCPEchoServer, tmp_path: Path) -> None:
    message = "Hello NetScope - TCP is reliable"
    log_path = tmp_path / "metrics.csv"
    response, elapsed_ms = echo(message, *tcp_server.address, logger=MetricsLogger(log_path))
    assert response == message
    assert elapsed_ms >= 0
    assert load_metrics(log_path)[0]["service"] == "echo"


def test_udp_lookup_returns_known_record(udp_server: UDPLookupServer, tmp_path: Path) -> None:
    log_path = tmp_path / "metrics.csv"
    answer, elapsed_ms = lookup("NeTsCoPe.LoCaL", *udp_server.address, logger=MetricsLogger(log_path))
    assert answer == "192.0.2.30"
    assert elapsed_ms >= 0
    assert load_metrics(log_path)[0]["protocol"] == "UDP"


def test_udp_lookup_returns_controlled_unknown_response(udp_server: UDPLookupServer) -> None:
    answer, _ = lookup("unknown.example", *udp_server.address)
    assert answer == "NOT_FOUND"


def test_tcp_file_transfer_preserves_content_and_hash(file_server: TCPFileServer, tmp_path: Path) -> None:
    source = tmp_path / "HelloWorld.txt"
    source.write_bytes((b"NetScope file-transfer test\n" * 800) + bytes(range(256)))
    log_path = tmp_path / "metrics.csv"

    result = transfer_file(source, *file_server.address, logger=MetricsLogger(log_path))

    destination = file_server.upload_dir / result.received_filename
    assert result.status == "success"
    assert result.bytes_transferred == source.stat().st_size
    assert destination.read_bytes() == source.read_bytes()
    assert result.sha256 == file_hash(destination)
    assert result.throughput_mbps >= 0
    summary = summarize(load_metrics(log_path))
    assert summary["successful_requests"] == 1
    assert summary["average_throughput_mbps"] >= 0


def test_five_concurrent_tcp_clients_complete(tcp_server: TCPEchoServer) -> None:
    results = run_concurrent_echoes(5, *tcp_server.address)
    assert len(results) == 5
    assert all(result.success for result in results)


def test_client_and_server_write_structured_metrics(tmp_path: Path) -> None:
    log_path = tmp_path / "metrics.csv"
    logger = MetricsLogger(log_path)
    server = TCPEchoServer(port=0, logger=logger)
    ready = threading.Event()
    thread = threading.Thread(target=server.serve_forever, args=(lambda _: ready.set(),), daemon=True)
    thread.start()
    assert ready.wait(2), "TCP server did not start"
    try:
        response, _ = echo("log both sides", *server.address, logger=logger)
        assert response == "log both sides"
    finally:
        server.shutdown()
        thread.join(timeout=2)

    rows = load_metrics(log_path)
    assert {row["actor"] for row in rows} == {"client", "server"}
