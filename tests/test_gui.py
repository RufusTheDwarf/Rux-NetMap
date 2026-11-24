"""Parcours réel Qt avec backend mémoire. Auteur : Onlyrutsuu."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QDialog
    from gui.dialogs import ConfirmDialog
    from gui.main_window import MainWindow
except ModuleNotFoundError as exc:
    if exc.name != "PySide6":
        raise
    QApplication = None

from tests.fakes import ADAPTER, IP, FakeNet, make_session


@unittest.skipUnless(QApplication, "Installe PySide6-Essentials pour les tests Qt.")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = FakeNet()
        self.window = MainWindow(self.backend, Path(self.tmp.name))
        self.addCleanup(self.window.close)

    def test_initial_state_and_consent_checkbox(self):
        self.assertEqual(self.window.cidr.text(), "192.168.42.0/24")
        self.assertFalse(self.window.tcp.isChecked())
        self.assertFalse(self.window.export_btn.isEnabled())
        self.assertFalse(self.backend.calls)
        dialog = ConfirmDialog(make_session().plan, self.window)
        self.assertFalse(dialog.launch.isEnabled())
        dialog.check.setChecked(True)
        self.assertTrue(dialog.launch.isEnabled())
        dialog.deleteLater()

    def test_rejected_confirmation_emits_no_probe(self):
        with patch.object(ConfirmDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            self.window.start_scan()
        self.assertFalse(self.backend.calls)
        self.assertIsNone(self.window.worker)

    def test_qt_scan_filter_numeric_sort_and_end_state(self):
        w = self.window
        for n in (2, 10):
            self.backend.macs[IP(f"192.168.42.{n}")] = f"00:50:56:00:00:{n:02X}"
        w.cidr.setText("192.168.42.0/28")
        w.dns.setChecked(False)
        def confirm():
            dlg = self.app.activeModalWidget()
            dlg.check.click()
            dlg.launch.click()
        QTimer.singleShot(0, confirm)
        w.start_scan()
        deadline = time.monotonic() + 10
        while w.worker is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertIsNone(w.worker)
        self.assertEqual(w.snapshot.status, "completed")
        self.assertEqual(w.proxy.rowCount(), 2)
        w.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(w.proxy.index(0, 0).data(), "192.168.42.2")
        w.search.setText(".10")
        self.assertEqual(w.proxy.rowCount(), 1)
        self.assertEqual(len(w.snapshot.devices), 2)
        self.assertTrue(w.export_btn.isEnabled())
        self.assertTrue(w.scan_btn.isEnabled())
        self.assertIn("Scan confirmé", w.log_text.toPlainText())

    def test_multiple_interfaces_require_choice(self):
        from dataclasses import replace
        self.backend.interfaces = (ADAPTER, replace(ADAPTER, guid="{other}", luid=31, index=3, name="VMware"))
        # Forget the previous explicit selection, as on an initial multi-NIC startup.
        self.window.adapter.setCurrentIndex(-1)
        self.window.refresh_adapters()
        self.assertFalse(self.window.scan_btn.isEnabled())
        self.window.adapter.setCurrentIndex(1)
        self.assertTrue(self.window.scan_btn.isEnabled())
