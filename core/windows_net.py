"""Adaptateur Windows x64 : IP Helper et cache DNS. Auteur : Onlyrutsuu.

Les structures utilisent les largeurs du SDK, y compris lors des tests ABI hors
Windows. Les buffers reçus restent en vie jusqu’à la fin de chaque parcours.
"""
import ctypes as C
import os
import socket
from ipaddress import IPv4Address, IPv4Interface
from uuid import UUID

from core.models import Adapter
from core.scope import private

U8, U16, U32, U64 = C.c_uint8, C.c_uint16, C.c_uint32, C.c_uint64
P, ptr = C.c_void_p, C.byref
AF = socket.AF_INET


class SockaddrIn(C.Structure):
    _fields_ = [("family", U16), ("port", U16), ("ip", U8 * 4), ("zero", U8 * 8)]


class Inet(C.Union):
    # SOCKADDR_INET also accommodates SOCKADDR_IN6 (28 bytes, alignment 4).
    _fields_ = [("v4", SockaddrIn), ("v6", U8 * 28), ("alignment", U32)]

    @classmethod
    def from_ip(cls, ip: IPv4Address):
        result = cls()
        result.v4.family = AF
        result.v4.ip[:] = ip.packed
        return result

    @property
    def ip(self):
        return IPv4Address(bytes(self.v4.ip)) if self.v4.family == AF else None


class SocketAddress(C.Structure):
    _fields_ = [("address", P), ("length", C.c_int32)]

    def ipv4(self):
        if not self.address or self.length < C.sizeof(SockaddrIn):
            return None
        sock = C.cast(self.address, C.POINTER(SockaddrIn)).contents
        return IPv4Address(bytes(sock.ip)) if sock.family == AF else None


class Unicast(C.Structure):
    _fields_ = [("length", U32), ("flags", U32), ("next", P), ("socket", SocketAddress),
                ("origin", U32), ("suffix", U32), ("dad", U32), ("valid", U32),
                ("preferred", U32), ("lease", U32), ("prefix", U8)]


class DnsServer(C.Structure):
    _fields_ = [("alignment", U64), ("next", P), ("socket", SocketAddress)]


class AdapterRow(C.Structure):
    # SDK prefix through NetworkGuid. Windows owns the variable-length tail.
    _fields_ = [
        ("length", U32), ("index", U32), ("next", P), ("guid", C.c_char_p),
        ("unicast", P), ("anycast", P), ("multicast", P), ("dns", P),
        ("dns_suffix", P), ("description", P), ("name", C.c_wchar_p),
        ("physical", U8 * 8), ("mac_len", U32), ("flags", U32),
        ("mtu", U32), ("kind", U32), ("status", U32), ("ipv6_index", U32),
        ("zones", U32 * 16), ("first_prefix", P), ("tx_speed", U64),
        ("rx_speed", U64), ("wins", P), ("gateway", P), ("metric4", U32),
        ("metric6", U32), ("luid", U64), ("dhcp4", SocketAddress),
        ("compartment", U32), ("network_guid", U8 * 16),
    ]


class Prefix(C.Structure):
    _fields_ = [("address", Inet), ("length", U8)]


class RouteRow(C.Structure):
    _fields_ = [("luid", U64), ("index", U32), ("prefix", Prefix), ("next_hop", Inet),
                ("site_prefix", U8), ("valid", U32), ("preferred", U32), ("metric", U32),
                ("protocol", U32), ("loopback", U8), ("autoconf", U8), ("publish", U8),
                ("immortal", U8), ("age", U32), ("origin", U32)]


class Neighbor(C.Structure):
    _fields_ = [("address", Inet), ("index", U32), ("luid", U64), ("physical", U8 * 32),
                ("mac_len", U32), ("state", U32), ("flags", U8), ("reachability", U32)]


class DnsRecord(C.Structure):
    # DNS_RECORDW header plus the PTR data variant.
    _fields_ = [("next", P), ("name", P), ("kind", U16), ("length", U16),
                ("flags", U32), ("ttl", U32), ("reserved", U32), ("ptr_name", C.c_wchar_p)]


def _nodes(pointer, structure):
    while pointer:
        node = C.cast(pointer, C.POINTER(structure)).contents
        yield node
        pointer = node.next


def _mac(raw, length):
    if length != 6:
        return None
    value = bytes(raw[:length])
    if value == bytes(6) or value[0] & 1:
        return None
    return value.hex(":").upper()


def _function(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype = result
    fn.argtypes = args
    return fn


def _error(code):
    return C.WinError(code)


class WindowsNet:
    def __init__(self):
        if os.name != "nt" or C.sizeof(P) != 8:
            raise OSError("RUX requiert Windows 10/11 et un processus x64.")
        api = C.WinDLL("iphlpapi", use_last_error=True)
        dns = C.WinDLL("dnsapi", use_last_error=True)
        self._list = _function(api, "GetAdaptersAddresses", U32, U32, U32, P, P, C.POINTER(U32))
        self._route = _function(api, "GetBestRoute2", U32, P, U32, P, P, U32, P, P)
        self._resolve = _function(api, "ResolveIpNetEntry2", U32, P, P)
        self._read_neighbor = _function(api, "GetIpNetEntry2", U32, P)
        self._icmp_open = _function(api, "IcmpCreateFile", P)
        self._icmp_close = _function(api, "IcmpCloseHandle", C.c_int32, P)
        self._icmp = _function(api, "IcmpSendEcho2Ex", U32, P, P, P, P, U32, U32,
                               P, U16, P, P, U32, U32)
        self._query = _function(dns, "DnsQuery_W", C.c_int32, C.c_wchar_p, U16, U32,
                                P, C.POINTER(P), P)
        self._free = _function(dns, "DnsFree", None, P, C.c_int)

    def adapters(self) -> tuple[Adapter, ...]:
        size = U32(15 * 1024)
        for _ in range(4):
            buf = C.create_string_buffer(size.value)
            # Ignore anycast and multicast records. Keep unicast and DNS servers.
            code = self._list(AF, 0x02 | 0x04, None, buf, ptr(size))
            if code == 232:  # ERROR_NO_DATA
                return ()
            if code == 111:  # ERROR_BUFFER_OVERFLOW during a configuration change
                continue
            if code:
                raise _error(code)
            return self._read_adapters(buf)
        raise OSError("La liste des cartes réseau change trop rapidement.")

    @staticmethod
    def _read_adapters(buf) -> tuple[Adapter, ...]:
        found = []
        for a in _nodes(C.addressof(buf), AdapterRow):
            if a.length < AdapterRow.network_guid.offset + 16 or a.status != 1:
                continue
            if a.kind not in (6, 71, 161) or not a.guid:
                continue  # Ethernet, Wi-Fi ou agrégat Ethernet avec lien actif.
            dns = tuple(dict.fromkeys(ip for d in _nodes(a.dns, DnsServer)
                                      if (ip := d.socket.ipv4()) is not None))
            for item in _nodes(a.unicast, Unicast):
                ip = item.socket.ipv4()
                if (item.length <= Unicast.prefix.offset or item.dad != 4 or ip is None
                        or item.prefix > 32 or not private(ip)):
                    continue
                found.append(Adapter(a.index, a.luid, a.guid.decode("ascii", "replace"),
                                     str(UUID(bytes_le=bytes(a.network_guid))), a.name or str(ip),
                                     IPv4Interface((ip, item.prefix)), _mac(a.physical, a.mac_len), dns))
        return tuple(sorted(found, key=lambda a: (a.name.casefold(), int(a.address.ip))))

    def on_link(self, adapter: Adapter, ip: IPv4Address) -> bool:
        src, dst = Inet.from_ip(adapter.address.ip), Inet.from_ip(ip)
        luid, route, best = U64(adapter.luid), RouteRow(), Inet()
        code = self._route(ptr(luid), adapter.index, ptr(src), ptr(dst), 0, ptr(route), ptr(best))
        if code:
            raise _error(code)
        return (route.luid == adapter.luid and route.index == adapter.index and
                route.prefix.length > 0 and route.next_hop.ip == IPv4Address(0) and
                best.ip == adapter.address.ip)

    def arp(self, adapter: Adapter, ip: IPv4Address) -> str | None:
        row = Neighbor()
        row.address = Inet.from_ip(ip)
        row.luid, row.index = adapter.luid, adapter.index
        src = Inet.from_ip(adapter.address.ip)
        code = self._resolve(ptr(row), ptr(src))
        if code in (67, 11010, 121, 1231):
            return None
        if code:
            raise _error(code)
        return _mac(row.physical, row.mac_len)

    def cached_mac(self, adapter: Adapter, ip: IPv4Address) -> str | None:
        """Lecture passive. L’appelant a déjà reçu un Echo Reply de cette IP."""
        row = Neighbor()
        row.address = Inet.from_ip(ip)
        row.luid, row.index = adapter.luid, adapter.index
        code = self._read_neighbor(ptr(row))
        if code in (2, 1168):
            return None
        if code:
            raise _error(code)
        if row.state not in (2, 3, 4, 5, 6) or row.flags & 2:
            return None
        return _mac(row.physical, row.mac_len)

    def echo(self, adapter: Adapter, ip: IPv4Address, timeout_ms: int) -> int | None:
        handle = self._icmp_open()
        if not handle or handle == P(-1).value:
            raise _error(C.get_last_error())
        # IP_OPTION_INFORMATION32: TTL=1, no options. Extra padding also fits
        # the native structure. The two IPAddr DWORDs contain network-order bytes.
        options = C.create_string_buffer(16)
        options[0] = b"\x01"
        reply = C.create_string_buffer(256)
        data = C.create_string_buffer(b"RUX")
        try:
            count = self._icmp(handle, None, None, None,
                               int.from_bytes(adapter.address.ip.packed, "little"),
                               int.from_bytes(ip.packed, "little"), data, 3, options,
                               reply, len(reply), timeout_ms)
            if not count:
                code = C.get_last_error()
                if code in (11002, 11003, 11004, 11005, 11010, 11013, 11018, 1231):
                    return None
                raise _error(code)
            # Echo reply address, status and round-trip time are the first 12 bytes.
            if reply.raw[:4] != ip.packed or U32.from_buffer(reply, 4).value != 0:
                return None
            return U32.from_buffer(reply, 8).value
        finally:
            self._icmp_close(handle)

    def cached_ptr(self, ip: IPv4Address) -> str | None:
        records = P()
        # DNS_QUERY_NO_WIRE_QUERY: restrict this call to local cache.
        code = self._query(ip.reverse_pointer + ".", 12, 0x10, None, ptr(records), None)
        try:
            if code in (9003, 9501, 9701):
                return None
            if code:
                raise _error(code)
            for item in _nodes(records.value, DnsRecord):
                if item.kind == 12 and item.ptr_name:
                    return item.ptr_name.rstrip(".")
            return None
        finally:
            if records:
                self._free(records, 1)  # DnsFreeRecordList
