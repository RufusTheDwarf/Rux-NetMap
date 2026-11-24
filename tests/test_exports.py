"""Exactitude et atomicité des exports. Auteur : Onlyrutsuu."""
import csv
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from agents.report import document, export
from core.models import Device, PortResult, Snapshot
from tests.fakes import IP, make_session


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        ts = "2026-01-01T09:00:00.000Z"
        device = Device(IP("192.168.42.2"), None, "ICMP", ts, ts, "swiss-école", "=formula",
                        1, (PortResult(443, "open"),))
        self.scan = Snapshot("abc", make_session(tcp=True).plan, ts, ts, "cancelled", 1, (device,), ())

    def test_csv_json_and_ui_record_match(self):
        p, q = self.root / "a.csv", self.root / "a.json"
        self.assertEqual(export(self.scan, p, "csv"), 1)
        self.assertEqual(export(self.scan, q, "json"), 1)
        result = json.loads(q.read_text("utf-8"))
        self.assertEqual(result, document(self.scan))
        self.assertEqual(result["application"]["author"], "Onlyrutsuu")
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual([r["record_type"] for r in rows], ["scan", "device"])
        self.assertEqual(rows[0]["status"], "cancelled")
        self.assertEqual(rows[1]["ip"], result["devices"][0]["ip"])
        self.assertEqual(rows[1]["hostname"], "swiss-école")
        self.assertEqual(rows[1]["vendor"], "'=formula")
        self.assertEqual(rows[1]["ports"], "443=open")

    def test_empty_partial_scan_export_is_identifiable(self):
        scan = replace(self.scan, devices=(), checked=0, status="failed")
        path = self.root / "a.csv"
        self.assertEqual(export(scan, path, "csv"), 0)
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["status"], rows[0]["observed"]), ("failed", "0"))

    def test_failed_write_leaves_original_and_no_temporary_file(self):
        path = self.root / "a.json"
        path.write_text("existant")
        with patch("skills.exports.os.replace", side_effect=PermissionError()), self.assertRaises(PermissionError):
            export(self.scan, path, "json")
        self.assertEqual(path.read_text(), "existant")
        self.assertEqual(list(self.root.iterdir()), [path])
