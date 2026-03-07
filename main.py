import argparse
import asyncio
import ipaddress
import os
import shlex
import socket
import sys
import time
from typing import List, Tuple


def validate_target(user_input: str) -> str:
    if not user_input:
        raise ValueError("No target specified.")
    try:
        ipaddress.ip_address(user_input)
        return user_input
    except ValueError:
        try:
            return socket.gethostbyname(user_input)
        except socket.gaierror:
            raise ValueError(
                f"'{user_input}' is neither a valid IP nor a resolvable hostname."
            )


async def scan_port(
    ip: str, port: int, timeout: float, semaphore: asyncio.Semaphore
) -> Tuple[int, str, str]:
    async with semaphore:
        for attempt in range(2):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port), timeout=timeout
                )
                banner = ""
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=0.5)
                    banner = data.decode("utf-8", errors="replace").strip()
                    banner = banner.splitlines()[0][:80] if banner else ""
                except Exception:
                    pass
                writer.close()
                await writer.wait_closed()
                return port, "open", banner
            except asyncio.TimeoutError:
                if attempt == 0:
                    continue
                return port, "filtered", ""
            except (ConnectionRefusedError, OSError):
                return port, "closed", ""
    return port, "closed", ""


async def scan_target(
    target: str, ports: List[int], concurrency: int, timeout: float
) -> None:
    try:
        ip = validate_target(target)
    except ValueError as e:
        print(f"  [!] Error: {e}")
        return

    total = len(ports)
    print(f"\n  Artemis scan report for {target} ({ip})")
    print(f"  Scanning {total} port(s)  •  concurrency {concurrency}  •  timeout {timeout}s\n")

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [scan_port(ip, port, timeout, semaphore) for port in ports]

    open_ports: List[Tuple[int, str, str]] = []
    filtered_count = 0
    closed_count = 0
    start_time = time.monotonic()

    try:
        for task in asyncio.as_completed(tasks):
            port, status, banner = await task
            if status == "open":
                try:
                    service = socket.getservbyport(port, "tcp")
                except OSError:
                    service = "unknown"
                open_ports.append((port, service, banner))
            elif status == "filtered":
                filtered_count += 1
            else:
                closed_count += 1
    except asyncio.CancelledError:
        print("  [!] Scan cancelled.")
        raise

    duration = time.monotonic() - start_time

    if open_ports:
        open_ports.sort()
        header = f"  {'PORT':<10}{'STATE':<10}{'SERVICE':<16}BANNER"
        print(header)
        print("  " + "─" * (len(header) + 10))
        for port, service, banner in open_ports:
            port_proto = f"{port}/tcp"
            print(f"  {port_proto:<10}{'open':<10}{service:<16}{banner}")
    else:
        print("  No open ports found.")

    not_shown = []
    if closed_count:
        not_shown.append(f"{closed_count} closed")
    if filtered_count:
        not_shown.append(f"{filtered_count} filtered")

    print()
    if not_shown:
        print(f"  Not shown: {', '.join(not_shown)} port(s)")
    print(f"  Scan completed in {duration:.2f}s  •  {len(open_ports)} open port(s) found\n")


def parse_ports(port_str: str) -> List[int]:
    ports = set()
    for part in port_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                if start > end:
                    start, end = end, start
                ports.update(range(start, end + 1))
            except ValueError:
                raise ValueError(f"Invalid port range syntax: '{part}'")
        else:
            try:
                ports.add(int(part))
            except ValueError:
                raise ValueError(f"Invalid port value: '{part}'")

    valid = sorted(p for p in ports if 1 <= p <= 65535)
    if not valid:
        raise ValueError("No valid ports found in the given input.")
    return valid


def _build_scan_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scan", description="Scan a target host for open ports.", add_help=True
    )
    parser.add_argument("target", help="Target IP or hostname")
    parser.add_argument(
        "-p", "--ports", default="1-1024",
        help="Ports to scan (default: 1-1024). Examples: 80,443 | 1-1024 | 22,80,1000-2000",
    )
    parser.add_argument(
        "-c", "--concurrency", type=int, default=500,
        help="Max simultaneous connections (default: 500)",
    )
    parser.add_argument(
        "-t", "--timeout", type=float, default=1.0,
        help="Socket timeout in seconds (default: 1.0)",
    )
    return parser


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        from banner import BANNER
        print(BANNER)
    except ImportError:
        pass

    scan_parser = _build_scan_parser()

    while True:
        try:
            raw = input("artemis> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[!] Exiting Artemis. Goodbye.")
            sys.exit(0)

        if not raw:
            continue

        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = raw.split()

        cmd = parts[0].lower()

        if cmd in ("exit", "quit", "q"):
            print("[*] Exiting Artemis. Goodbye.")
            sys.exit(0)

        if cmd == "help":
            try:
                from help import HELP
                print(HELP)
            except ImportError:
                print("[!] Help module not found.")
            continue

        if cmd == "clear":
            os.system("cls" if sys.platform == "win32" else "clear")
            continue

        if cmd == "scan":
            try:
                args = scan_parser.parse_args(parts[1:])
            except SystemExit:
                continue
            try:
                ports_list = parse_ports(args.ports)
            except ValueError as e:
                print(f"[!] {e}")
                continue
            try:
                asyncio.run(
                    scan_target(args.target, ports_list, args.concurrency, args.timeout)
                )
            except KeyboardInterrupt:
                print("\n[!] Scan interrupted by user.")
            continue

        print(f"[!] Unknown command: '{cmd}'. Type 'help' for usage.")


if __name__ == "__main__":
    main()
