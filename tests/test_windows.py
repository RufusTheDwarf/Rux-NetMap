"""ABI du SDK et interrogation passive sur Windows. Auteur : Onlyrutsuu."""
import ctypes as C
import os
import unittest
from unittest.mock import Mock

from core import windows_net as win
from tests.fakes import ADAPTER, IP


class WindowsABITests(unittest.TestCase):
    @unittest.skipUnless(C.sizeof(C.c_void_p) == 8, "Cible x64")
    def test_windows_sdk_layout(self):
        for typ, expected in ((win.Inet, 28), (win.RouteRow, 104), (win.Neighbor, 88),
                              (win.SocketAddress, 16), (win.Unicast, 64)):
            self.assertEqual(C.sizeof(typ), expected, typ.__name__)
        self.assertEqual(win.AdapterRow.luid.offset, 224)
        self.assertEqual(win.AdapterRow.network_guid.offset, 252)
        self.assertEqual(win.DnsRecord.ptr_name.offset, 32)
        self.assertEqual(win.Unicast.prefix.offset, 56)
        self.assertEqual(win.RouteRow.next_hop.offset, 44)

    def test_adapter_fixture_ipv4_prefix_and_luid(self):
        address = win.Inet.from_ip(ADAPTER.address.ip)
        unicast = win.Unicast()
        unicast.length, unicast.dad, unicast.prefix = C.sizeof(unicast), 4, 24
        unicast.socket = win.SocketAddress(C.addressof(address), 16)
        row = win.AdapterRow()
        row.length = C.sizeof(row)
        row.index, row.luid, row.name, row.guid = 7, 42, "Ethernet", b"{test}"
        row.status, row.kind, row.unicast = 1, 6, C.addressof(unicast)
        row.mac_len, row.physical[:6] = 6, bytes.fromhex("005056040506")
        result, = win.WindowsNet._read_adapters(row)
        self.assertEqual(str(result.address), "192.168.42.20/24")
        self.assertEqual((result.index, result.luid, result.mac), (7, 42, "00:50:56:04:05:06"))
        row.status = 2
        self.assertFalse(win.WindowsNet._read_adapters(row))

    def test_only_on_link_route_with_right_source_and_interface(self):
        api = object.__new__(win.WindowsNet)
        hop = "0.0.0.0"
        def route(luid, index, src, dst, options, out, best):
            row = C.cast(out, C.POINTER(win.RouteRow)).contents
            row.luid, row.index, row.prefix.length = ADAPTER.luid, index, 24
            row.next_hop = win.Inet.from_ip(IP(hop))
            C.memmove(best, src, C.sizeof(win.Inet))
            return 0
        api._route = route
        self.assertTrue(api.on_link(ADAPTER, IP("192.168.42.2")))
        hop = "192.168.42.1"
        self.assertFalse(api.on_link(ADAPTER, IP("192.168.42.2")))

    def test_icmp_native_buffer_and_reply_source(self):
        api = object.__new__(win.WindowsNet)
        ip = IP("192.168.42.2")
        api._icmp_open = lambda: 123
        api._icmp_close = Mock()
        reply_source = ip.packed
        def send(handle, event, apc, ctx, source, dest, payload, count, opts, reply, size, timeout):
            self.assertEqual(source.to_bytes(4, "little"), ADAPTER.address.ip.packed)
            self.assertEqual(dest.to_bytes(4, "little"), ip.packed)
            self.assertEqual((opts.raw[0], count, timeout), (1, 3, 400))
            C.memmove(reply, reply_source + bytes(4) + (14).to_bytes(4, "little"), 12)
            return 1
        api._icmp = send
        self.assertEqual(api.echo(ADAPTER, ip, 400), 14)
        reply_source = IP("192.168.42.1").packed
        self.assertIsNone(api.echo(ADAPTER, ip, 400))
        self.assertEqual(api._icmp_close.call_count, 2)

    def test_native_arp_is_bound_to_confirmed_adapter(self):
        api = object.__new__(win.WindowsNet)
        ip = IP("192.168.42.3")
        def resolve(out, src):
            row = C.cast(out, C.POINTER(win.Neighbor)).contents
            self.assertEqual((row.luid, row.index, row.address.ip), (ADAPTER.luid, ADAPTER.index, ip))
            self.assertEqual(C.cast(src, C.POINTER(win.Inet)).contents.ip, ADAPTER.address.ip)
            row.physical[:6], row.mac_len = bytes.fromhex("005056010203"), 6
            return 0
        api._resolve = resolve
        self.assertEqual(api.arp(ADAPTER, ip), "00:50:56:01:02:03")
        api._resolve = lambda *args: 67
        self.assertIsNone(api.arp(ADAPTER, ip))

    def test_native_dns_cache_only_and_record_release(self):
        api = object.__new__(win.WindowsNet)
        record = win.DnsRecord()
        record.kind, record.ptr_name = 12, "host.lan."
        def query(name, kind, flags, extra, out, reserved):
            self.assertEqual((name, kind, flags), ("2.42.168.192.in-addr.arpa.", 12, 0x10))
            C.cast(out, C.POINTER(C.c_void_p))[0] = C.addressof(record)
            return 0
        api._query, api._free = query, Mock()
        self.assertEqual(api.cached_ptr(IP("192.168.42.2")), "host.lan")
        api._free.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "Nécessite les DLL natives de Windows")
    def test_native_windows_bindings_and_passive_enumeration(self):
        api = win.WindowsNet()
        for adapter in api.adapters():
            self.assertGreater(adapter.index, 0)
            self.assertTrue(win.private(adapter.address.ip))
