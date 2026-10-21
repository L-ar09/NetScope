# NetScope

NetScope is a local network experimentation project. Day 1 implements the foundation services: a TCP echo service and an educational UDP name lookup service. Both bind to the loopback interface by default, so they do not expose services to the local network.

## Setup

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the services

Use separate terminals for each server and client.

```powershell
python -m server.tcp_echo_server
python -m client.tcp_echo_client "Hello NetScope!"

python -m server.udp_lookup_server
python -m client.udp_lookup_client netscope.local
python -m client.udp_lookup_client unknown.example
```

Expected results: the TCP client prints the exact message it sent; known UDP names return their configured documentation-only address, while unknown names return `NOT_FOUND`.

## Verify

```powershell
python -m pytest
```

The tests start each service on an ephemeral loopback port and cover TCP echo, known UDP records, and the controlled unknown-domain response.

## Day 1 implementation notes

- TCP echo: `127.0.0.1:5001`
- UDP lookup: `127.0.0.1:5003`
- Lookup data: `data/dns_records.json`
- The lookup service is a simulation, not a DNS server or source of real DNS data.

Future folders (`monitoring`, `dashboard`, `data/uploads`, and `data/captures`) are present for the following project phases.
