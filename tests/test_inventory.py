"""Historique SQLite et changements d’adresse. Auteur : Onlyrutsuu."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from core.inventory import Inventory
from core.models import Device
from tests.fakes import ADAPTER, IP


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Inventory(Path(self.tmp.name) / "i.sqlite3")
        self.addCleanup(self.db.close)
        self.one = Device(IP("192.168.42.2"), "00:50:56:00:00:02", "ARP", "2026-01-01", "2026-01-01")

    def test_mac_reappears_under_new_ip(self):
        self.db.remember(ADAPTER, self.one)
        d = replace(self.one, ip=IP("192.168.42.3"), first_seen="2026-02-01", last_seen="2026-02-01")
        result = self.db.remember(ADAPTER, d)
        self.assertEqual((result.first_seen, result.last_seen), ("2026-01-01", "2026-02-01"))

    def test_reordered_observations_never_shrink_history(self):
        self.db.remember(ADAPTER, replace(self.one, first_seen="2026-06-01", last_seen="2026-06-01"))
        result = self.db.remember(ADAPTER, self.one)
        self.assertEqual((result.first_seen, result.last_seen), ("2026-01-01", "2026-06-01"))

    def test_unknown_mac_different_profile_and_reused_ip(self):
        self.db.remember(ADAPTER, self.one)
        newer = replace(self.one, first_seen="2026-02-01", last_seen="2026-02-01")
        for a, d in ((ADAPTER, replace(newer, mac=None)),
                     (ADAPTER, replace(newer, mac="00:50:56:00:00:09")),
                     (replace(ADAPTER, network_guid="other"), newer)):
            self.assertEqual(self.db.remember(a, d).first_seen, "2026-02-01")
