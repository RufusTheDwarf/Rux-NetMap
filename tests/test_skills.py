"""Contrats des skills réseau, OUI et journal. Auteur : Onlyrutsuu."""
import logging
import socket
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.scope import TargetDenied
from skills.arp import skill_arp_scan
from skills.dns import _ptr_answer, skill_dns_resolve
from skills.icmp import skill_icmp_ping
from skills.journal import open_journal, skill_logging
from skills.oui import load_registry, skill_oui_lookup
from skills.tcp import skill_tcp_probe
from tests.fakes import IP, make_session


def name_wire(name):
    return b"".join(bytes([len(x)]) + x.encode() for x in name.split(".")) + b"\0"


def reply(query, ident=3):
    target = name_wire("printer.lan")
    return (struct.pack("!6H", ident, 0x8400, 1, 1, 0, 0) + name_wire(query) +
            struct.pack("!HH", 12, 1) + b"\xc0\x0c" +
            struct.pack("!HHIH", 12, 1, 120, len(target)) + target)


class SkillTests(unittest.TestCase):
    def test_arp_and_icmp_include_zero_latency(self):
        s = make_session()
        ip = IP("192.168.42.2")
        s.backend.macs[ip] = "00:50:56:00:00:02"
        s.backend.echoes[ip] = 0
        self.assertEqual(skill_arp_scan(s, ip), s.backend.macs[ip])
        self.assertEqual(skill_icmp_ping(s, ip), 0)
        self.assertIsNone(skill_arp_scan(s, IP("192.168.42.4")))

    def test_oui_supports_all_prefix_lengths_and_private_macs(self):
        db = {"001122": "L", "0011223": "M", "001122334": "S"}
        for mac, vendor in (("00:11:22:33:4F:FF", "S"), ("00-11-22-31-FF-FF", "M"),
                            ("0011224FFFFF", "L"), ("02:11:22:33:44:55", None),
                            ("01:11:22:33:44:55", None), ("invalid", None), (None, None)):
            self.assertEqual(skill_oui_lookup(mac, db), vendor)
        self.assertIn("VMware", skill_oui_lookup("00:50:56:01:02:03", load_registry()))

    def test_tcp_only_confirmed_ports(self):
        for s, port in ((make_session(), 80), (make_session(tcp=True), 22)):
            with patch("skills.tcp.socket.socket") as factory, self.assertRaises(TargetDenied):
                skill_tcp_probe(s, IP("192.168.42.2"), port)
            factory.assert_not_called()

    def test_tcp_states_timeouts_pinning_and_no_payload(self):
        for exc, state in ((None, "open"), (ConnectionRefusedError(), "refused"),
                           (TimeoutError(), "indeterminate")):
            s = make_session(tcp=True)
            with patch("skills.tcp.socket.socket") as factory:
                sock = factory.return_value.__enter__.return_value
                sock.connect.side_effect = exc
                self.assertEqual(skill_tcp_probe(s, IP("192.168.42.2"), 443).state, state)
                sock.bind.assert_called_once_with(("192.168.42.20", 0))
                sock.settimeout.assert_called_once_with(0.35)
                sock.setsockopt.assert_any_call(socket.IPPROTO_IP, socket.IP_TTL, 1)
                sock.send.assert_not_called()

    def test_dns_cache_does_not_emit_network_query(self):
        ip = IP("192.168.42.2")
        s = make_session(dns=True)
        s.backend.names[ip] = "rux.test"
        with patch("skills.dns.socket.socket") as factory:
            self.assertEqual(skill_dns_resolve(s, ip), "rux.test")
            factory.assert_not_called()

    def test_dns_disabled_or_no_authorized_server(self):
        for s in (make_session(dns=False), make_session("192.168.42.2/32", dns=True)):
            with patch("skills.dns.socket.socket") as factory:
                self.assertIsNone(skill_dns_resolve(s, IP("192.168.42.2")))
                factory.assert_not_called()

    def test_dns_direct_local_ptr_non_recursive(self):
        s = make_session(dns=True)
        ip = IP("192.168.42.2")
        with patch("skills.dns.socket.socket") as factory, patch("skills.dns.secrets.randbits", return_value=3):
            sock = factory.return_value.__enter__.return_value
            sock.recv.return_value = reply(ip.reverse_pointer)
            self.assertEqual(skill_dns_resolve(s, ip), "printer.lan")
            sock.connect.assert_called_once_with(("192.168.42.1", 53))
            self.assertEqual(sock.send.call_args.args[0][2:4], b"\0\0")
        s.backend.indirect.add(IP("192.168.42.1"))
        with patch("skills.dns.socket.socket") as factory, self.assertRaises(TargetDenied):
            skill_dns_resolve(s, ip)
        factory.assert_not_called()

    def test_dns_rejects_mismatched_truncated_and_cyclic_answers(self):
        query = "2.42.168.192.in-addr.arpa"
        good = reply(query)
        for packet in (reply(query, 4), good[:-1], good[:2] + b"\x86\x00" + good[4:],
                       good[:12] + b"\xc0\x0c" + good[14:], reply("3.42.168.192.in-addr.arpa")):
            self.assertIsNone(_ptr_answer(packet, 3, query))
        self.assertEqual(_ptr_answer(good, 3, query), "printer.lan")

    def test_logging_delivers_matching_utc_event_to_ui_and_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            view = []
            log = open_journal(Path(tmp), view.append)
            try:
                skill_logging(log, logging.INFO, "scan1", "un\ndeux")
                self.assertIn("[scan1] un deux", view[0])
                self.assertIn(view[0], (Path(tmp) / "rux.log").read_text(encoding="utf-8"))
            finally:
                for handler in log.handlers:
                    handler.close()
