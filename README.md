# 🔍 Artemis — Async TCP Port Scanner

Artemis is a lightweight, fast, asynchronous TCP port scanner built in Python. It is designed for network reconnaissance — identifying open ports, detecting running services, and grabbing banners from live hosts. It operates through an interactive shell interface, making it comfortable for both quick one-off scans and exploratory sessions.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Starting the Shell](#starting-the-shell)
  - [Commands](#commands)
  - [Scan Examples](#scan-examples)
- [Port Syntax Reference](#port-syntax-reference)
- [Architecture & Design Decisions](#architecture--design-decisions)
- [Module & File Structure](#module--file-structure)
- [Function Reference](#function-reference)
- [Output Format](#output-format)
- [Limitations](#limitations)
- [Disclaimer](#disclaimer)

---

## Features

- ⚡ **Asynchronous scanning** — hundreds of ports scanned concurrently using Python's `asyncio`
- 🔎 **Banner grabbing** — captures the first line of any data sent by an open port
- 🧠 **Service detection** — maps open ports to well-known service names via the OS service database
- 🛡️ **Input validation** — validates both IP addresses and hostnames before scanning
- 🖥️ **Interactive shell** — persistent REPL-style interface with `scan`, `help`, `clear`, and `exit` commands
- ⚙️ **Configurable** — adjust concurrency, timeout, and port ranges per scan
- 🪟 **Cross-platform** — works on Linux, macOS, and Windows

---

## Requirements

- Python **3.8** or higher (for `asyncio.run()` and `asyncio.as_completed()`)
- No third-party dependencies — the entire project uses the Python standard library only

---

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/artemis.git
cd artemis

# No pip install needed — zero external dependencies
python main.py
```

---

## Usage

### Starting the Shell

```bash
python main.py
```

This launches the interactive Artemis shell:

```
artemis>
```

If a `banner.py` file exists in the project root and exports a `BANNER` string, it will be printed at startup.

---

### Commands

| Command   | Description                                      |
|-----------|--------------------------------------------------|
| `scan`    | Run a port scan against a target host            |
| `help`    | Display usage information (from `help.py`)       |
| `clear`   | Clear the terminal screen                        |
| `exit`    | Exit the Artemis shell (also: `quit`, `q`)       |

---

### Scan Examples

**Scan the default port range (1–1024) on a host:**
```
artemis> scan 192.168.1.1
```

**Scan specific ports:**
```
artemis> scan example.com -p 22,80,443
```

**Scan a custom range with increased concurrency:**
```
artemis> scan 10.0.0.5 -p 1-65535 -c 1000
```

**Scan with a longer timeout (useful on slow networks):**
```
artemis> scan scanme.nmap.org -p 1-1024 -t 2.0
```

**Mix individual ports and ranges:**
```
artemis> scan 172.16.0.1 -p 22,80,1000-2000,8080,9000-9100
```

---

### Scan Flags

| Flag                    | Default    | Description                                         |
|-------------------------|------------|-----------------------------------------------------|
| `target`                | *(required)* | IP address or hostname to scan                    |
| `-p`, `--ports`         | `1-1024`   | Port(s) to scan. Supports ranges and comma lists    |
| `-c`, `--concurrency`   | `500`      | Maximum simultaneous TCP connections                |
| `-t`, `--timeout`       | `1.0`      | Seconds to wait before marking a port as filtered   |

---

## Port Syntax Reference

Artemis accepts flexible port specifications:

| Syntax             | Meaning                              |
|--------------------|--------------------------------------|
| `80`               | Single port                          |
| `80,443,8080`      | Multiple individual ports            |
| `1-1024`           | All ports from 1 to 1024 (inclusive) |
| `22,80,1000-2000`  | Mix of individual and range          |

- Duplicate ports are automatically deduplicated
- Ports outside the valid range (1–65535) are silently ignored
- Ranges specified in reverse order (e.g., `1024-1`) are automatically corrected

---

## Architecture & Design Decisions

### Why `asyncio`?

Port scanning is fundamentally an **I/O-bound task** — most of the time spent scanning is waiting for the network to respond (or time out). Traditional threaded approaches introduce significant overhead from context switching when hundreds of threads are active simultaneously.

Python's `asyncio` solves this by using a single-threaded **event loop** that can manage thousands of concurrent connections cooperatively. Rather than blocking on each connection, Artemis suspends a coroutine the moment it starts waiting and immediately picks up another one. This results in dramatically higher throughput with lower memory usage compared to `threading` or `multiprocessing`.

### Why a `Semaphore`?

Even with async I/O, opening too many simultaneous connections can exhaust the OS file descriptor limit or overwhelm the target network. The `asyncio.Semaphore` acts as a concurrency throttle — it allows up to `N` ports to be actively connecting at once, while the rest wait their turn. This makes scanning both polite and stable at high concurrency levels.

### Why `shlex.split()` for input parsing?

The interactive shell uses `shlex.split()` to tokenize user input rather than a naive `.split()`. This is important because it correctly handles quoted strings (e.g., hostnames or arguments with spaces), matching how a real Unix shell tokenizes commands. If `shlex` fails (e.g., on malformed quotes), the code gracefully falls back to a plain `.split()` so the shell never crashes on bad input.

### Why `argparse` for scan commands?

Re-using `argparse` inside an interactive shell gives the `scan` command professional-grade argument parsing for free — including `--help`, type validation, defaults, and error messages — without writing a custom parser. The `_build_scan_parser()` function builds the parser once at startup, and it is reused across every scan invocation.

### Why retry on `asyncio.TimeoutError`?

A single packet loss can cause a legitimately open port to appear filtered. Artemis makes **two connection attempts** before marking a port as filtered. This is a simple heuristic that significantly reduces false negatives on unreliable networks without adding meaningful overhead, since the second attempt only runs if the first times out.

### Why standard library only?

Keeping Artemis dependency-free means it can be dropped onto any system with Python 3.8+ and run immediately — no `pip install`, no virtual environments, no version conflicts. This is a deliberate design choice for a tool that is often used in environments where installing packages may be restricted.

---

## Module & File Structure

```
artemis/
│
├── main.py          # Core application: shell loop, scan logic, argument parsing
├── banner.py        # (Optional) Exports a BANNER string printed at startup
└── help.py          # (Optional) Exports a HELP string shown by the 'help' command
```

**`main.py`** contains the entire scanning engine and interactive shell. The optional `banner.py` and `help.py` modules are loaded at runtime via `try/except ImportError`, so Artemis runs correctly whether or not they are present.

---

## Function Reference

### `validate_target(user_input: str) -> str`

Validates and resolves a user-provided target before scanning begins.

- First attempts to parse the input as a raw IP address using `ipaddress.ip_address()`.
- If that fails, treats the input as a hostname and resolves it to an IP via `socket.gethostbyname()`.
- Raises `ValueError` with a descriptive message if the input is neither a valid IP nor a resolvable hostname.
- Returns the resolved IP address string, which is used for all subsequent connection attempts.

---

### `scan_port(ip, port, timeout, semaphore) -> Tuple[int, str, str]`

An `async` coroutine that performs a single TCP connection attempt against one port.

- Acquires the shared `semaphore` before connecting, ensuring concurrency stays within the configured limit.
- Attempts to connect up to **two times** before giving up, to reduce false-positive "filtered" results from transient packet loss.
- On a successful connection, waits up to **0.5 seconds** for a banner — the first line of any data the server sends — and returns it alongside the port number and `"open"` status.
- Returns `"filtered"` if both attempts time out, or `"closed"` if the connection is actively refused.
- Banner text is decoded as UTF-8 (with error replacement), stripped of whitespace, and capped at 80 characters to keep output readable.

---

### `scan_target(target, ports, concurrency, timeout) -> None`

The top-level `async` coroutine that orchestrates a complete scan against a host.

- Calls `validate_target()` to resolve the target and exits early with an error if it is invalid.
- Creates one `scan_port` coroutine task per port and submits them all using `asyncio.as_completed()`, which yields results as they finish rather than waiting for the slowest one.
- Tracks results into three buckets: `open_ports`, `filtered_count`, and `closed_count`.
- For each open port, calls `socket.getservbyport()` to look up the conventional service name (e.g., `22 → ssh`, `80 → http`).
- Prints a formatted results table after all tasks complete, followed by a summary line showing counts and elapsed time.

---

### `parse_ports(port_str: str) -> List[int]`

Parses a flexible, comma-separated port specification string into a sorted list of valid port integers.

- Splits the input on commas and processes each segment individually.
- Handles hyphenated ranges (e.g., `1000-2000`) by expanding them into a full integer set; automatically corrects reversed ranges.
- Deduplicates all ports using a `set`.
- Filters out any ports outside the valid TCP range of 1–65535.
- Raises `ValueError` with a descriptive message for any unrecognizable segment, and if the final list is empty.

---

### `_build_scan_parser() -> argparse.ArgumentParser`

A factory function that constructs and returns the `argparse` parser for the `scan` command.

- Configures four arguments: a required positional `target`, and optional `-p`/`--ports`, `-c`/`--concurrency`, and `-t`/`--timeout` flags.
- Called once at application startup so the parser object can be reused across every scan invocation without being rebuilt.

---

### `main() -> None`

The application entry point and interactive REPL loop.

- On Windows, sets the `WindowsProactorEventLoopPolicy` to enable TCP connections in the asyncio event loop, which is required on that platform.
- Attempts to import and print a startup banner from `banner.py`.
- Runs an infinite `while True` loop, reading user input and dispatching to the appropriate handler based on the first token of the command.
- Handles `KeyboardInterrupt` and `EOFError` (e.g., `Ctrl+C` / `Ctrl+D`) gracefully with a clean exit message.
- Unknown commands print a helpful error nudging the user toward `help`.

---

## Output Format

A successful scan produces output in the following format:

```
  Artemis scan report for scanme.nmap.org (45.33.32.156)
  Scanning 1024 port(s)  •  concurrency 500  •  timeout 1.0s

  PORT      STATE     SERVICE         BANNER
  ──────────────────────────────────────────────────────────
  22/tcp    open      ssh             SSH-2.0-OpenSSH_6.6.1p1
  80/tcp    open      http            

  Not shown: 989 closed, 33 filtered port(s)
  Scan completed in 3.41s  •  2 open port(s) found
```

- Only **open** ports are shown in the table; closed and filtered ports are summarised in a count line.
- The **BANNER** column shows the first line returned by the service on connection, which often reveals the software name and version.
- Results are sorted numerically by port number for readability.

---

## Limitations

- **TCP only** — Artemis performs TCP connect scans exclusively. UDP scanning is not supported.
- **No OS fingerprinting** — service names come from the local OS database, not active probing.
- **Single target per scan** — each `scan` command targets one host. Subnet or CIDR range scanning is not currently supported.
- **No output file** — scan results are printed to stdout only. Redirecting with `>` in your shell will capture them if needed.

---

## Disclaimer

Artemis is intended for use on networks and systems **you own or have explicit written permission to test**. Unauthorized port scanning may be illegal in your jurisdiction and violates the terms of service of most networks. The authors accept no responsibility for misuse of this tool.
