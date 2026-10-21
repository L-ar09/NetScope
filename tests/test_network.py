"""Day 1 end-to-end tests against real loopback sockets."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from client.concurrent_test import run_concurrent_echoes
from client.tcp_file_client import transfer_file
from client.tcp_echo_client import echo
from client.udp_lookup_client import lookup
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


def test_tcp_echo_returns_exact_message(tcp_server: TCPEchoServer) -> None:
    message = "Hello NetScope - TCP is reliable"
    response, elapsed_ms = echo(message, *tcp_server.address)
    assert response == message
    assert elapsed_ms >= 0


def test_udp_lookup_returns_known_record(udp_server: UDPLookupServer) -> None:
    answer, elapsed_ms = lookup("NeTsCoPe.LoCaL", *udp_server.address)
    assert answer == "192.0.2.30"
    assert elapsed_ms >= 0


def test_udp_lookup_returns_controlled_unknown_response(udp_server: UDPLookupServer) -> None:
    answer, _ = lookup("unknown.example", *udp_server.address)
    assert answer == "NOT_FOUND"


def test_tcp_file_transfer_preserves_content_and_hash(file_server: TCPFileServer, tmp_path: Path) -> None:
    source = tmp_path / "HelloWorld.txt"
    source.write_bytes((b"NetScope file-transfer test\n" * 800) + bytes(range(256)))

    result = transfer_file(source, *file_server.address)

    destination = file_server.upload_dir / result.received_filename
    assert result.status == "success"
    assert result.bytes_transferred == source.stat().st_size
    assert destination.read_bytes() == source.read_bytes()
    assert result.sha256 == file_hash(destination)
    assert result.throughput_mbps >= 0


def test_five_concurrent_tcp_clients_complete(tcp_server: TCPEchoServer) -> None:
    results = run_concurrent_echoes(5, *tcp_server.address)
    assert len(results) == 5
    assert all(result.success for result in results)
