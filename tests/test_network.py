"""Day 1 end-to-end tests against real loopback sockets."""

from __future__ import annotations

import threading

import pytest

from client.tcp_echo_client import echo
from client.udp_lookup_client import lookup
from server.tcp_echo_server import TCPEchoServer
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
