# NetScope Testing Guide

This guide lists the commands used to test each NetScope feature. Run every command from the project root:

```text
C:\Users\larya\Developer\NetScope
```

## Prepare each PowerShell terminal

Open a new PowerShell terminal in the project folder and activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

The prompt should begin with `(.venv)`.

## Automated verification

Run all automated tests:

```powershell
python -m pytest
```

Expected result:

```text
10 passed
```

## TCP echo service

Terminal 1 - start the TCP echo server:

```powershell
python -m server.tcp_echo_server
```

Terminal 2 - send a message:

```powershell
python -m client.tcp_echo_client "Hello NetScope!"
```

Expected result: the client receives the exact same message and shows a response time.

Test a failed TCP connection by ensuring the server is stopped, then using an unused port:

```powershell
python -m client.tcp_echo_client "Failure test" --port 5999
```

## UDP lookup service

Terminal 1 - start the UDP lookup server:

```powershell
python -m server.udp_lookup_server
```

Terminal 2 - query a known record:

```powershell
python -m client.udp_lookup_client netscope.local
```

Expected result:

```text
Resolved IP: 192.0.2.30
```

Query an unknown record:

```powershell
python -m client.udp_lookup_client unknown.example
```

Expected result:

```text
Resolved IP: NOT_FOUND
```

Test a UDP timeout by ensuring the lookup server is stopped, then using an unused port:

```powershell
python -m client.udp_lookup_client netscope.local --port 5999
```

Expected result:

```text
Lookup timed out
```

## TCP file transfer

Terminal 1 - start the file-transfer server:

```powershell
python -m server.tcp_file_server
```

Terminal 2 - send a file. This example transfers the project README:

```powershell
python -m client.tcp_file_client .\README.md
```

Expected result: status `success`, the byte count, SHA-256 verification result, duration, and throughput. The received file is saved in:

```text
data\uploads\
```

## Concurrent TCP clients

Start the TCP echo server first:

```powershell
python -m server.tcp_echo_server
```

In a second terminal, run five parallel clients:

```powershell
python -m client.concurrent_test --clients 5
```

Expected result:

```text
Completed: 5/5 successful
```

Change `5` to test another workload, for example `--clients 10`.

## Application metrics

After running one or more clients, print the application-level summary:

```powershell
python -m monitoring.metrics
```

Open `data\metrics.csv` in Excel to inspect individual request records. This file is generated automatically and may be deleted when you want to start a fresh measurement set.

## Fault injection and diagnosis

Fault settings are stored in `data\fault_config.json`. Servers reload the file before each request, so you can change one setting while a server is running. Restore every value to its default after an experiment.

Simulate a 500 ms application delay:

```json
{
  "delay_ms": 500,
  "udp_drop_probability": 0.0,
  "wrong_lookup": false,
  "tcp_disconnect": false
}
```

Simulate a UDP response drop on every request:

```json
{
  "delay_ms": 0,
  "udp_drop_probability": 1.0,
  "wrong_lookup": false,
  "tcp_disconnect": false
}
```

Simulate an incorrect lookup result:

```json
{
  "delay_ms": 0,
  "udp_drop_probability": 0.0,
  "wrong_lookup": true,
  "tcp_disconnect": false
}
```

Simulate a TCP disconnect before the normal response:

```json
{
  "delay_ms": 0,
  "udp_drop_probability": 0.0,
  "wrong_lookup": false,
  "tcp_disconnect": true
}
```

After a fault experiment, inspect the metrics and diagnosis:

```powershell
python -m monitoring.metrics
python -m monitoring.diagnosis
```

Important: a simulated UDP response drop means the application deliberately did not reply. It is not proof that a network packet was lost. Use a matching `.pcapng` capture when making packet-level conclusions.

## Dashboard

After producing application metrics or packet-export CSV files, start the local dashboard:

```powershell
python -m streamlit run dashboard/app.py
```

Open the local address printed by Streamlit, normally `http://localhost:8501`. The dashboard shows client request counts, success rate, application response-time charts, file-transfer throughput, diagnostic findings, and summaries for capture CSV files in `data\captures\`.

The **Fault controls** section edits `data\fault_config.json`. Save a configuration, run a new request, and use **Refresh data** to see its recorded outcome. Restore all fault values to zero or `false` after an experiment.

## TShark capture

List the available capture interfaces:

```powershell
python -m monitoring.capture --list-interfaces
```

For NetScope localhost traffic, use the interface named `NPF_Loopback` (currently interface `9`).

Terminal 1 - start the TCP echo server:

```powershell
python -m server.tcp_echo_server
```

Terminal 2 - begin a 15-second packet capture:

```powershell
python -m monitoring.capture --capture .\data\captures\tcp_echo.pcapng --interface 9 --capture-filter "tcp port 5001" --duration 15
```

While the capture is running, use Terminal 3 to generate traffic:

```powershell
python -m client.tcp_echo_client "Packet capture test"
```

The saved capture is:

```text
data\captures\tcp_echo.pcapng
```

Use a different filter for other services:

```powershell
# TCP file transfer
--capture-filter "tcp port 5002"

# UDP lookup
--capture-filter "udp port 5003"
```

## Export a capture to CSV

Export selected packet fields from a TCP echo capture:

```powershell
python -m monitoring.capture --export .\data\captures\tcp_echo.pcapng --output .\data\captures\tcp_echo_export.csv --display-filter "tcp.port == 5001"
```

Analyze the exported packet evidence:

```powershell
python -m monitoring.packet_analyzer .\data\captures\tcp_echo_export.csv
```

For the other services, use these display filters:

```powershell
# TCP file transfer
--display-filter "tcp.port == 5002"

# UDP lookup
--display-filter "udp.port == 5003"
```

## Open a capture in Wireshark

Open Wireshark, choose **File -> Open**, and select the `.pcapng` file under `data\captures\`.

Useful Wireshark display filters:

```text
tcp.port == 5001
tcp.port == 5002
udp.port == 5003
tcp.flags.syn == 1
tcp.analysis.retransmission
tcp.analysis.ack_rtt
```

## Stopping a server

In the terminal that is running a server, press:

```text
Ctrl + C
```
