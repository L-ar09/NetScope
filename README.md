# NetScope

NetScope is a local network experimentation platform for learning and demonstrating core Computer Networks concepts. It provides working TCP and UDP services, measures application response time and file-transfer throughput, and gives a structured foundation for later packet analysis, fault experiments, and a monitoring dashboard.

All currently implemented services bind to `127.0.0.1` by default. They communicate only within the same computer and do not expose ports to other devices on the network.

## Project objectives

- Demonstrate reliable, connection-oriented TCP communication.
- Demonstrate connectionless UDP request and response communication.
- Transfer files using a framed TCP protocol and verify their integrity.
- Exercise a TCP server with multiple simultaneous clients.
- Build toward reproducible network measurements, packet forensics, controlled fault injection, and visual diagnostics.

## Architecture

```text
TCP Echo Client ──────────────── TCP Echo Server       (port 5001)
Concurrent Echo Clients ───────┘

TCP File Client ──────────────── TCP File Server       (port 5002)
                                      │
                                      └── data/uploads/

UDP Lookup Client ────────────── UDP Lookup Server     (port 5003)
                                      │
                                      └── data/dns_records.json
```

## Implemented features

### TCP echo service

The TCP echo client connects to the server, sends a UTF-8 message, receives the exact same message, and measures round-trip response time. The server handles every accepted connection in a separate thread.

- Server: `server/tcp_echo_server.py`
- Client: `client/tcp_echo_client.py`
- Address: `127.0.0.1:5001`

### UDP lookup service

The UDP lookup service is an educational DNS-style simulation, not a real DNS resolver. The client sends a domain-like name, and the server returns a configured documentation-only address or `NOT_FOUND`.

- Server: `server/udp_lookup_server.py`
- Client: `client/udp_lookup_client.py`
- Address: `127.0.0.1:5003`
- Records: `data/dns_records.json`

### TCP file transfer

The file-transfer client sends a file to the server. The server saves it under `data/uploads/`, calculates its SHA-256 digest, and returns an acknowledgement. The client reports the transfer duration and throughput in Mbps.

- Server: `server/tcp_file_server.py`
- Client: `client/tcp_file_client.py`
- Address: `127.0.0.1:5002`
- Destination: `data/uploads/`

The transfer protocol uses explicit framing because TCP is a byte stream and does not preserve message boundaries:

```text
[4-byte metadata length]
[JSON metadata: filename, size, SHA-256]
[exactly file-size bytes]
[framed JSON acknowledgement]
```

### Concurrent-client test

The concurrent-client runner creates multiple TCP echo clients in parallel. Each client sends a unique message and reports its own result and response time.

- Runner: `client/concurrent_test.py`
- Default workload: five simultaneous clients

### Structured metrics and performance summary

Each command-line client records one structured CSV row in `data/metrics.csv`. Server processes also record their handling results when started from the command line. Records include a request identifier, timestamp, actor, protocol, service, status, application response time, transferred bytes, throughput, and any error type.

Use the metrics summary command after running one or more clients:

```powershell
python -m monitoring.metrics
```

It reports total requests, successful and timed-out requests, success and timeout rates, average response time, and average transfer throughput. These values are application-level measurements; they are not packet-level Wireshark measurements.

## Project structure

```text
NetScope/
├── client/                 # TCP, UDP, file-transfer, and concurrency clients
├── server/                 # TCP echo, TCP file-transfer, and UDP lookup services
├── data/
│   ├── dns_records.json    # Simulated lookup records
│   ├── uploads/            # Files received by the TCP file server
│   └── captures/           # Reserved for Wireshark packet captures
├── monitoring/             # Structured CSV logging and performance summaries
├── dashboard/              # Reserved for Streamlit visualizations
├── tests/                  # Automated loopback integration tests
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

## Running the services

Use separate PowerShell terminals for a server and its client. Activate `.venv` in each terminal before running a command.

### TCP echo

```powershell
# Terminal 1
python -m server.tcp_echo_server

# Terminal 2
python -m client.tcp_echo_client "Hello NetScope!"
```

The client prints the echoed message and its response time.

### UDP lookup

```powershell
# Terminal 1
python -m server.udp_lookup_server

# Terminal 2
python -m client.udp_lookup_client netscope.local
python -m client.udp_lookup_client unknown.example
```

Known records return a configured address. Unknown records return `NOT_FOUND`.

### File transfer

```powershell
# Terminal 1
python -m server.tcp_file_server

# Terminal 2
python -m client.tcp_file_client .\path\to\your-file.txt
```

The client displays the saved filename, byte count, SHA-256 verification result, elapsed time, and throughput. The received file appears in `data/uploads/`.

### Concurrent clients

Start the TCP echo server first, then run:

```powershell
python -m client.concurrent_test --clients 5
```

Change `5` to test a different number of simultaneous clients.

## Testing

Run the automated integration tests with:

```powershell
New-Item -ItemType Directory -Force .\tmp | Out-Null
python -m pytest --basetemp .\tmp\pytest
```

The test suite uses real loopback sockets and verifies:

- exact TCP echo responses;
- known and unknown UDP lookup results;
- file content preservation and SHA-256 integrity verification;
- successful handling of five concurrent TCP clients.

## Planned extensions

The repository includes dedicated locations for the following capabilities:

- Wireshark capture files and packet-level observations;
- configurable delay, response-drop, incorrect-lookup, and disconnect experiments;
- a Streamlit dashboard for charts, diagnostics, and service comparisons.

## Important terminology

Application response time is the time measured by these client programs from sending a request to receiving a reply. It is not the same as packet-level TCP round-trip time measured from a network capture. Similarly, an application timeout does not by itself prove network packet loss.
