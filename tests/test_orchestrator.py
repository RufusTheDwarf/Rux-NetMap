"""Cycle de vie, dégradation, limite globale et annulation. Auteur : Onlyrutsuu."""
import logging
import tempfile
import threading
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from agents.orchestrator import run_scan
from core.scope import Consent, plan_scan
from tests.fakes import ADAPTER, IP, FakeNet


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.back = FakeNet()
        self.cancel = Event()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.logger = logging.Logger("test")
        self.logger.addHandler(logging.NullHandler())
        self.rows, self.counts = [], []

    def scan(self, cidr="192.168.42.0/29", tcp=False, dns=False, seen=None):
        plan = plan_scan(ADAPTER, cidr, tcp, dns, 200)
        return run_scan(Consent(plan, accepted=True), self.back, self.cancel, Path(self.tmp.name),
                        self.logger, seen or self.rows.append, lambda n, total: self.counts.append(n))

    def test_inventory_observations_and_gui_callbacks(self):
        self.back.macs[IP("192.168.42.2")] = "00:50:56:12:34:56"
        self.back.echoes[IP("192.168.42.3")] = 0
        snapshot = self.scan()
        self.assertEqual(snapshot.status, "completed")
        self.assertEqual(snapshot.checked, 6)
        self.assertEqual(len(self.rows), 2)
        self.assertEqual(self.counts, list(range(1, 7)))
        self.assertEqual([(d.method, d.latency_ms) for d in snapshot.devices], [("ARP", None), ("ICMP", 0)])
        self.assertIn("VMware", snapshot.devices[0].vendor)

    def test_local_address_recorded_without_arp_or_echo(self):
        snapshot = self.scan("192.168.42.20/32")
        self.assertEqual(snapshot.devices[0].method, "local")
        self.assertEqual(self.back.calls, [])

    def test_neighbor_cache_enriches_only_fresh_echo_replies(self):
        self.back.neighbors = {IP("192.168.42.2"): "00:50:56:00:00:02",
                               IP("192.168.42.3"): "00:50:56:00:00:03"}
        self.back.echoes[IP("192.168.42.3")] = 1
        scan = self.scan()
        self.assertEqual([(d.ip, d.mac, d.method) for d in scan.devices],
                         [(IP("192.168.42.3"), "00:50:56:00:00:03", "ICMP")])

    def test_ports_never_applied_to_unobserved_hosts(self):
        self.back.echoes[IP("192.168.42.2")] = 5
        from core.models import PortResult
        with patch("agents.identification.skill_tcp_probe",
                   side_effect=lambda s, ip, p: PortResult(p, "refused")) as tcp:
            snapshot = self.scan(tcp=True)
        self.assertEqual([x.args[1:] for x in tcp.call_args_list], [(IP("192.168.42.2"), 80),
                                                                    (IP("192.168.42.2"), 443)])
        self.assertEqual(len(snapshot.devices), 1)

    def test_permissions_degrade_once_and_keep_icmp(self):
        self.back.echoes[IP("192.168.42.2")] = 3
        with patch("core.config.MAX_WORKERS", 1), patch.object(self.back, "arp",
                side_effect=PermissionError("denied")) as arp:
            snapshot = self.scan()
        self.assertEqual(arp.call_count, 1)
        self.assertEqual(snapshot.status, "partial")
        self.assertEqual(len(snapshot.notices), 1)
        self.assertEqual(snapshot.devices[0].method, "ICMP")

    def test_cancel_stops_scheduling_and_preserves_observed_rows(self):
        self.back.macs[IP("192.168.42.1")] = "00:50:56:00:00:01"
        def stop(device):
            self.rows.append(device)
            self.cancel.set()
        with patch("core.config.MAX_WORKERS", 1):
            snapshot = self.scan(seen=stop)
        self.assertEqual((snapshot.status, snapshot.checked, len(snapshot.devices)), ("cancelled", 1, 1))
        self.assertEqual({ip for _, ip in self.back.calls}, {IP("192.168.42.1")})

    def test_cancellation_during_enrichment_keeps_host(self):
        self.back.macs[IP("192.168.42.1")] = "00:50:56:00:00:01"
        self.back.cached_ptr = lambda ip: self.cancel.set()
        with patch("core.config.MAX_WORKERS", 1), patch("skills.dns.socket.socket") as factory:
            snapshot = self.scan(tcp=True, dns=True)
        self.assertEqual(snapshot.status, "cancelled")
        self.assertEqual(len(snapshot.devices), 1)
        factory.assert_not_called()

    def test_withdrawn_interface_before_scan_or_during_scan(self):
        self.back.interfaces = ()
        first = self.scan()
        self.assertEqual(first.status, "failed")
        self.assertFalse(self.back.calls)
        self.cancel.clear()
        self.back.interfaces = (ADAPTER,)
        self.back.macs[IP("192.168.42.1")] = "00:50:56:00:00:01"
        def disconnect(device):
            self.back.interfaces = ()
        with patch("core.config.MAX_WORKERS", 1):
            second = self.scan(seen=disconnect)
        self.assertEqual((second.status, second.checked), ("partial", 1))
        self.assertEqual(len(second.devices), 1)

    def test_indirect_target_skipped_not_probed(self):
        only = IP("192.168.42.2")
        self.back.indirect.add(only)
        scan = self.scan("192.168.42.2/32")
        self.assertFalse(self.back.calls)
        self.assertEqual(scan.status, "partial")

    def test_global_worker_limit(self):
        lock = threading.Lock()
        counters = {"active": 0, "peak": 0}
        def hold(adapter, ip):
            with lock:
                counters["active"] += 1
                counters["peak"] = max(counters["peak"], counters["active"])
            time.sleep(0.012)
            with lock:
                counters["active"] -= 1
            return None
        self.back.arp = hold
        snapshot = self.scan("192.168.42.32/27")
        self.assertEqual(snapshot.checked, 30)
        self.assertGreater(counters["peak"], 1)
        self.assertLessEqual(counters["peak"], 8)
