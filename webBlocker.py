import re
import socketserver
from xmlrpc import server
from dnslib import DNSRecord, RR, A, AAAA, QTYPE, RCODE
import socket
import platform
import subprocess
import time

redirectIp = "127.0.0.1"
redirectIpv6 = "::1"
upstreamDns = ("8.8.8.8", 53)
_dns_restore_state = None

class DNSSetupError(RuntimeError):
    pass

class ReusableUDPServer(socketserver.UDPServer):
    allow_reuse_address = True

def is_windows():
    return platform.system() == "Windows"

def run_command(command):
    return subprocess.run(command, check=True, capture_output=True, text=True, timeout=15)

def get_command_error(exc):
    return exc.stderr.strip() if exc.stderr else exc.stdout.strip() if exc.stdout else str(exc)

def parse_netsh_table(output):
    rows = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("Idx") or stripped.startswith("---"):
            continue
        parts = re.split(r"\s{2,}", stripped)
        if parts:
            rows.append(parts)
    return rows

def get_windows_interfaces():
    try:
        result = run_command(["netsh", "interface", "ipv4", "show", "interfaces"]).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []

    interfaces = []
    for parts in parse_netsh_table(result):
        if len(parts) < 5:
            continue
        try:
            idx = int(parts[0])
        except ValueError:
            continue
        interfaces.append({
            "idx": idx,
            "metric": parts[1],
            "mtu": parts[2],
            "state": parts[3].lower(),
            "name": parts[4],
        })
    return interfaces

def run_powershell_command(command):
    return run_command([
        "powershell", "-NoProfile", "-NonInteractive", "-Command", command
    ])

def _windows_interface_arg(iface):
    return f'name="{iface}"'

def _configure_windows_dns(iface, server_address, address_family):
    iface_arg = _windows_interface_arg(iface)
    if address_family == "IPv4":
        try:
            run_command([
                "netsh", "interface", "ipv4", "set", "dnsservers",
                iface_arg, "static", server_address, "primary", "validate=no"
            ])
            return
        except subprocess.CalledProcessError:
            pass

        command = (
            f'Set-DnsClientServerAddress -InterfaceAlias "{iface}" '
            f'-ServerAddresses {server_address} -AddressFamily IPv4'
        )
    else:
        try:
            run_command([
                "netsh", "interface", "ipv6", "set", "dnsservers",
                iface_arg, "static", server_address, "primary", "validate=no"
            ])
            return
        except subprocess.CalledProcessError:
            pass

        command = (
            f'Set-DnsClientServerAddress -InterfaceAlias "{iface}" '
            f'-ServerAddresses "{server_address}" -AddressFamily IPv6'
        )

    run_powershell_command(command)

def _reset_windows_dns(iface, address_family):
    iface_arg = _windows_interface_arg(iface)
    if address_family == "IPv4":
        try:
            run_command([
                "netsh", "interface", "ipv4", "set", "dnsservers",
                iface_arg, "dhcp", "validate=no"
            ])
            return
        except subprocess.CalledProcessError:
            pass

        command = (
            f'Set-DnsClientServerAddress -InterfaceAlias "{iface}" '
            f'-ResetServerAddresses -AddressFamily IPv4'
        )
    else:
        try:
            run_command([
                "netsh", "interface", "ipv6", "set", "dnsservers",
                iface_arg, "dhcp", "validate=no"
            ])
            return
        except subprocess.CalledProcessError:
            pass

        command = (
            f'Set-DnsClientServerAddress -InterfaceAlias "{iface}" '
            f'-ResetServerAddresses -AddressFamily IPv6'
        )

    run_powershell_command(command)

def set_dns_to_local(iface):
    global _dns_restore_state

    if is_windows():
        try:
            _configure_windows_dns(iface, redirectIp, "IPv4")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise DNSSetupError(f"Failed to set DNS on interface '{iface}': {get_command_error(exc)}")

        try:
            _configure_windows_dns(iface, redirectIpv6, "IPv6")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            print(f"[WARNING] IPv6 DNS redirect failed for '{iface}'; continuing with IPv4 only: {get_command_error(exc)}")

        _dns_restore_state = {"method": "windows", "iface": iface}
        return

    if shutil_which("resolvectl"):
        run_command(["resolvectl", "dns", iface, redirectIp])
        _dns_restore_state = {"method": "resolvectl", "iface": iface}
        return

    if shutil_which("nmcli"):
        connection = get_active_connection_name()
        if not connection:
            raise DNSSetupError("Unable to determine active NetworkManager connection.")
        run_command(["nmcli", "connection", "modify", connection, "ipv4.ignore-auto-dns", "yes"])
        run_command(["nmcli", "connection", "modify", connection, "ipv4.dns", redirectIp])
        run_command(["nmcli", "connection", "up", connection])
        _dns_restore_state = {"method": "nmcli", "connection": connection}
        return

    raise DNSSetupError("Linux DNS blocking requires either 'resolvectl' or 'nmcli'.")

def reset_dns(iface):
    global _dns_restore_state

    if not _dns_restore_state:
        return

    if _dns_restore_state["method"] == "windows":
        try:
            _reset_windows_dns(iface, "IPv4")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise DNSSetupError(f"Failed to reset DNS on interface '{iface}': {get_command_error(exc)}")

        try:
            _reset_windows_dns(iface, "IPv6")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
    elif _dns_restore_state["method"] == "resolvectl":
        run_command(["resolvectl", "revert", _dns_restore_state["iface"]])
    elif _dns_restore_state["method"] == "nmcli":
        connection = _dns_restore_state["connection"]
        run_command(["nmcli", "connection", "modify", connection, "ipv4.ignore-auto-dns", "no"])
        run_command(["nmcli", "connection", "modify", connection, "ipv4.dns", ""])
        run_command(["nmcli", "connection", "up", connection])

    _dns_restore_state = None

def get_active_interface():
    if is_windows():
        interfaces = get_windows_interfaces()
        if not interfaces:
            return None

        interfaces_by_idx = {entry["idx"]: entry for entry in interfaces}

        try:
            routes_output = run_command(["netsh", "interface", "ipv4", "show", "route"]).stdout
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            routes_output = ""

        default_candidates = []
        for parts in parse_netsh_table(routes_output):
            if len(parts) < 6 or parts[3] != "0.0.0.0/0":
                continue
            try:
                metric = int(parts[2])
                idx = int(parts[4])
            except ValueError:
                continue
            entry = interfaces_by_idx.get(idx)
            if entry and entry["state"] == "connected" and "loopback" not in entry["name"].lower():
                default_candidates.append((metric, entry["name"]))

        if default_candidates:
            default_candidates.sort(key=lambda item: item[0])
            return default_candidates[0][1]

        for entry in interfaces:
            if entry["state"] == "connected" and "loopback" not in entry["name"].lower():
                return entry["name"]
        return None

    try:
        result = run_command(["ip", "route", "show", "default"]).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    for line in result.splitlines():
        parts = line.split()
        if "dev" in parts:
            return parts[parts.index("dev") + 1]
    return None

def get_active_connection_name():
    try:
        result = run_command(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"]).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    iface = get_active_interface()
    for line in result.splitlines():
        if not line:
            continue
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        name, device = parts
        if device == iface:
            return name
    return None

def shutil_which(command):
    from shutil import which
    return which(command)

def matches(domain, pattern):
    domain = domain.lower().strip(".")
    pattern = pattern.lower().strip(".")

    if pattern.startswith("*."):
        pattern = pattern[2:]
        return domain == pattern or domain.endswith("." + pattern)

    return domain == pattern or domain.endswith("." + pattern)

class DNSHandler(socketserver.BaseRequestHandler):
    block_list = []

    def handle(self):
        data, sock = self.request
        request = DNSRecord.parse(data)

        qname = str(request.q.qname).rstrip(".").lower()

        blocked = any(matches(qname, pattern) for pattern in self.block_list)

        if blocked:
            reply = request.reply()
            qtype = QTYPE.get(request.q.qtype)
            if qtype == "A":
                reply.add_answer(RR(qname, QTYPE.A, rdata=A(redirectIp), ttl=60))
            elif qtype == "AAAA":
                reply.add_answer(RR(qname, QTYPE.AAAA, rdata=AAAA(redirectIpv6), ttl=60))
            else:
                reply.header.rcode = RCODE.NXDOMAIN
            sock.sendto(reply.pack(), self.client_address)
            print(f"[BLOCKED] {qname}")
        else:
            upstreamSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            upstreamSock.settimeout(5)
            try:
                upstreamSock.sendto(data, upstreamDns)
                response, _ = upstreamSock.recvfrom(512)
                sock.sendto(response, self.client_address)
            except socket.timeout:
                print(f"[DNS TIMEOUT] Upstream lookup failed for {qname}")
            finally:
                upstreamSock.close()

def run_dns_server(blockList, duration=None):
    iface = get_active_interface()
    if not iface:
        raise DNSSetupError("No active network interface found.")

    DNSHandler.block_list = blockList

    server = ReusableUDPServer(("0.0.0.0", 53), DNSHandler)

    print("DNS blocker running...")

    try:
        set_dns_to_local(iface)
        if duration:
            endTime = time.time() + duration
            server.timeout = 1
            while time.time() < endTime:
                server.handle_request()
        else:
            server.serve_forever()
    finally:
        print("Restoring DNS...")
        try:
            reset_dns(iface)
        finally:
            server.server_close()