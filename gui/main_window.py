"""Fenêtre d’inventaire, journal et gestion du scan. Auteur : Onlyrutsuu."""
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox,
    QStackedWidget, QTableView, QVBoxLayout, QWidget)

from agents import report
from core import config
from core.scope import Consent, ScopeError, plan_scan, suggested
from gui.device_table import DeviceFilter, DeviceTable
from gui.dialogs import About, ConfirmDialog
from gui.network_map import NetworkMap
from gui.worker import ScanWorker
from skills.journal import open_journal, skill_logging


class _Events(QObject):
    log = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self, backend, directory: Path, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.directory = directory
        self.worker = None
        self.snapshot = None
        self.wants_close = False
        self.setWindowTitle("RUX · Inventaire réseau")
        self.resize(1220, 760)
        self.setMinimumSize(820, 550)
        shell = QWidget()
        self.setCentralWidget(shell)
        layout = QHBoxLayout(shell)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(152)
        nav = QVBoxLayout(rail)
        nav.setContentsMargins(12, 24, 12, 16)
        brand = QLabel(config.APP)
        brand.setObjectName("brand")
        nav.addWidget(brand)
        nav.addSpacing(16)
        self.pages = QStackedWidget()
        self.nav_group = QButtonGroup(self)
        for i, title in enumerate(("Inventaire", "Carte du réseau", "Journal", "À propos")):
            btn = QPushButton(title)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            self.nav_group.addButton(btn, i)
            nav.addWidget(btn)
        self.nav_group.idClicked.connect(self.pages.setCurrentIndex)
        self.nav_group.button(0).setChecked(True)
        nav.addStretch()
        author = QLabel(config.AUTHOR)
        author.setObjectName("railCredit")
        nav.addWidget(author)
        layout.addWidget(rail)
        layout.addWidget(self.pages, 1)

        self.pages.addWidget(self._inventory_page())
        self.network_map = NetworkMap()
        self.network_map.device_requested.connect(self._show_device)
        self.pages.addWidget(self.network_map)
        logs = QWidget()
        logbox = QVBoxLayout(logs)
        logbox.setContentsMargins(20, 16, 20, 16)
        title = QLabel("Journal")
        title.setObjectName("pageTitle")
        logbox.addWidget(title)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setAccessibleName("Journal des événements de RUX")
        self.log_text.setMaximumBlockCount(2500)
        logbox.addWidget(self.log_text)
        self.pages.addWidget(logs)
        about = About()
        about.layout().setContentsMargins(20, 16, 20, 16)
        self.pages.addWidget(about)
        self.events = _Events(self)
        self.events.log.connect(self.log_text.appendPlainText)
        self.logger = open_journal(directory, self.events.log.emit)
        self.refresh_adapters()

    def _inventory_page(self):
        page = QWidget()
        body = QVBoxLayout(page)
        body.setContentsMargins(20, 16, 20, 12)
        body.setSpacing(10)
        title = QLabel("Inventaire réseau")
        title.setObjectName("pageTitle")
        body.addWidget(title)

        panel = QFrame()
        panel.setObjectName("panel")
        grid = QGridLayout(panel)
        grid.setContentsMargins(14, 10, 14, 12)
        self.adapter = QComboBox()
        self.adapter.setMinimumContentsLength(15)
        self.cidr = QLineEdit()
        self.cidr.setPlaceholderText("192.168.1.0/24")
        self.refresh_btn = QPushButton("Actualiser")
        self.refresh_btn.clicked.connect(self.refresh_adapters)
        self.tcp = QCheckBox("Ports TCP 80 et 443")
        self.dns = QCheckBox("Résolution DNS locale")
        self.dns.setChecked(True)
        self.timeout = QSpinBox()
        self.timeout.setRange(config.MIN_TIMEOUT_MS, config.MAX_TIMEOUT_MS)
        self.timeout.setValue(config.TIMEOUT_MS)
        self.timeout.setSuffix(" ms")
        self.timeout.setSingleStep(50)
        self.timeout.setToolTip("Délai des requêtes ICMP, TCP et DNS. Windows gère le délai ARP.")
        for col, (label, widget) in enumerate((("Interface", self.adapter), ("Plage IPv4", self.cidr),
                                                ("Délai", self.timeout))):
            lbl = QLabel(label)
            lbl.setBuddy(widget)
            grid.addWidget(lbl, 0, col)
            grid.addWidget(widget, 1, col)
        grid.addWidget(self.refresh_btn, 1, 3)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        options = QHBoxLayout()
        options.addWidget(self.dns)
        options.addWidget(self.tcp)
        options.addStretch()
        grid.addLayout(options, 2, 0, 1, 4)
        self.adapter.currentIndexChanged.connect(self._adapter_changed)
        body.addWidget(panel)

        actions = QHBoxLayout()
        self.scan_btn = QPushButton("Lancer le scan")
        self.scan_btn.setObjectName("primary")
        self.scan_btn.clicked.connect(self.start_scan)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.clicked.connect(self.cancel_scan)
        self.cancel_btn.setEnabled(False)
        actions.addWidget(self.scan_btn)
        actions.addWidget(self.cancel_btn)
        actions.addStretch()
        self.export_btn = QPushButton("Exporter")
        self.export_btn.setEnabled(False)
        exports = QMenu(self.export_btn)
        for kind in ("csv", "json"):
            exports.addAction(kind.upper()).triggered.connect(lambda checked=False, k=kind: self.export(k))
        self.export_btn.setMenu(exports)
        actions.addWidget(self.export_btn)
        body.addLayout(actions)

        self.summary = QLabel("Aucun scan lancé.")
        self.summary.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.bar.setFixedHeight(6)
        self.bar.setAccessibleName("Progression du scan")
        body.addWidget(self.summary)
        body.addWidget(self.bar)

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Filtrer par IP, nom, MAC ou fabricant…")
        self.search.setAccessibleName("Filtrer les appareils")
        body.addWidget(self.search)
        self.model = DeviceTable(self)
        self.proxy = DeviceFilter(self.model, self)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.table = QTableView()
        self.table.setAccessibleName("Appareils observés")
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, width in enumerate((125, 145, 150, 175, 85, 155, 155, 155)):
            self.table.setColumnWidth(col, width)
        body.addWidget(self.table, 1)
        return page

    @Slot(object)
    def _show_device(self, ip):
        for row, (device, _) in enumerate(self.model.rows):
            if device.ip != ip:
                continue
            source = self.model.index(row, 0)
            index = self.proxy.mapFromSource(source)
            if not index.isValid():
                self.search.clear()
                index = self.proxy.mapFromSource(source)
            self.nav_group.button(0).setChecked(True)
            self.pages.setCurrentIndex(0)
            self.table.setCurrentIndex(index)
            self.table.selectRow(index.row())
            self.table.scrollTo(index)
            self.table.setFocus()
            return

    def refresh_adapters(self):
        if self.worker is not None:
            return
        previous = self.adapter.currentData()
        self.adapter.blockSignals(True)
        self.adapter.clear()
        try:
            if self.backend is None:
                raise OSError("Les fonctions réseau nécessitent Windows x64.")
            for a in self.backend.adapters():
                self.adapter.addItem(f"{a.name}  ·  {a.address}", a)
        except OSError as exc:
            skill_logging(self.logger, logging.WARNING, "app", str(exc))
        self.adapter.blockSignals(False)
        if self.adapter.count():
            selected = next((i for i in range(self.adapter.count()) if self.adapter.itemData(i) == previous), -1)
            if selected < 0 and self.adapter.count() == 1:
                selected = 0
            self.adapter.setPlaceholderText("Choisir une interface…")
            self.adapter.setCurrentIndex(selected)
        else:
            self.adapter.setPlaceholderText("Aucune interface IPv4 privée active")
        self._adapter_changed()
        if self.adapter.count():
            self.statusBar().showMessage("Prêt" if self.adapter.currentData() else "Choisis une interface.")
        else:
            self.statusBar().showMessage("Connecte une carte Ethernet ou Wi-Fi privée, puis clique sur Actualiser.")

    def _adapter_changed(self, *_):
        a = self.adapter.currentData()
        self.cidr.setText(str(suggested(a)) if a else "")
        self.scan_btn.setEnabled(a is not None and self.worker is None)
        if a:
            self.cidr.setToolTip(f"Réseau détecté : {a.address.network}")

    def start_scan(self):
        a = self.adapter.currentData()
        if self.worker is not None or a is None:
            return
        try:
            plan = plan_scan(a, self.cidr.text(), self.tcp.isChecked(), self.dns.isChecked(),
                             self.timeout.value())
        except ScopeError as exc:
            QMessageBox.warning(self, "Plage ou paramètres invalides", str(exc))
            return
        dialog = ConfirmDialog(plan, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted and dialog.check.isChecked()
        dialog.deleteLater()
        if not accepted:
            return
        self.snapshot = None
        self.model.reset_scan(bool(plan.ports))
        self.network_map.set_plan(plan)
        self.search.clear()
        self.bar.setRange(0, len(plan.targets))
        self.bar.setValue(0)
        self.active_cidr = str(plan.network)
        self.export_btn.setEnabled(False)
        self._set_running(True)
        self._progress(0, len(plan.targets))
        self.statusBar().showMessage("Scan en cours")
        self.worker = ScanWorker(Consent(plan, accepted=True), self.backend, self.directory, self.logger, self)
        queued = Qt.ConnectionType.QueuedConnection
        self.worker.device.connect(self.model.add, queued)
        self.worker.device.connect(self.network_map.observe, queued)
        self.worker.progress.connect(self._progress, queued)
        self.worker.result.connect(self._result, queued)
        self.worker.failure.connect(self._failed, queued)
        self.worker.finished.connect(self._finished, queued)
        self.worker.start()

    def _set_running(self, running):
        for widget in (self.adapter, self.cidr, self.refresh_btn, self.timeout, self.dns, self.tcp):
            widget.setEnabled(not running)
        self.scan_btn.setEnabled(not running and self.adapter.currentData() is not None)
        self.cancel_btn.setEnabled(running)

    def cancel_scan(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_btn.setEnabled(False)
            self.statusBar().showMessage("Annulation demandée. Fin des opérations déjà engagées…")

    @Slot(int, int)
    def _progress(self, done, total):
        self.bar.setValue(done)
        self.summary.setText(f"{self.active_cidr}   ·   {done} / {total} adresses traitées"
                             f"   ·   {self.model.rowCount()} appareil(s) observé(s)")
        self.network_map.status.setText(self.summary.text())

    @Slot(object)
    def _result(self, snapshot):
        self.snapshot = snapshot
        labels = {"completed": "Terminé", "partial": "Partiel", "cancelled": "Annulé · résultat partiel",
                  "failed": "Échec"}
        summary = (f"{labels[snapshot.status]}   ·   {snapshot.plan.network}   ·   "
                   f"{snapshot.checked} / {len(snapshot.plan.targets)} adresses traitées   ·   "
                   f"{len(snapshot.devices)} appareil(s) observé(s)")
        if snapshot.notices:
            summary += "   ·   Voir le journal"
        self.summary.setText(summary)
        self.network_map.status.setText(summary)
        self.statusBar().showMessage(labels[snapshot.status])
        self.export_btn.setEnabled(True)

    @Slot(str)
    def _failed(self, message):
        self.summary.setText(f"Échec du scan. {message}")
        self.network_map.status.setText(self.summary.text())
        self.statusBar().showMessage("Échec · voir le journal")

    @Slot()
    def _finished(self):
        worker = self.worker
        self.worker = None
        if worker:
            worker.deleteLater()
        self._set_running(False)
        if self.wants_close:
            QTimer.singleShot(0, self.close)

    def export(self, kind):
        if self.snapshot is None:
            return
        filename = f"RUX-{self.snapshot.scan_id[:8]}.{kind}"
        dlg = QFileDialog(self, f"Exporter en {kind.upper()}")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setNameFilter(f"{kind.upper()} (*.{kind})")
        dlg.setDefaultSuffix(kind)
        dlg.selectFile(filename)
        chosen = dlg.selectedFiles() if dlg.exec() else []
        dlg.deleteLater()
        if not chosen:
            return
        path = Path(chosen[0])
        try:
            count = report.export(self.snapshot, path, kind)
        except (OSError, ValueError) as exc:
            skill_logging(self.logger, logging.ERROR, self.snapshot.scan_id, f"Échec export : {exc}")
            QMessageBox.warning(self, "Export impossible", str(exc))
            return
        skill_logging(self.logger, logging.INFO, self.snapshot.scan_id,
                      f"Export {kind.upper()} : {count} appareil(s) vers {path.name}.")
        self.statusBar().showMessage(f"Exporté : {path}", 12000)

    def closeEvent(self, event):
        if self.worker is not None:
            if not self.wants_close:
                answer = QMessageBox.question(self, "Scan en cours", "Annuler le scan et fermer RUX ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                self.wants_close = answer == QMessageBox.StandardButton.Yes
            if self.wants_close:
                self.cancel_scan()
            event.ignore()
            return
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
        event.accept()
