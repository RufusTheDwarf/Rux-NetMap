"""Carte des adresses du scan confirmé. Auteur : Onlyrutsuu."""
from ipaddress import IPv4Address

from PySide6.QtCore import QSize, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from core.models import Device, Plan


class NetworkMap(QWidget):
    """Affiche uniquement les cibles du plan et les observations du moteur de scan."""

    device_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cells: dict[IPv4Address, QListWidgetItem] = {}
        self.observed: dict[IPv4Address, Device] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        title = QLabel("Carte des adresses")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.segment = QLabel("Lance un scan depuis l’inventaire pour afficher sa plage.")
        self.segment.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.segment)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.grid = QListWidget()
        self.grid.setObjectName("addressGrid")
        self.grid.setAccessibleName("Carte des adresses IPv4 du scan")
        self.grid.setFlow(QListView.Flow.LeftToRight)
        self.grid.setWrapping(True)
        self.grid.setMovement(QListView.Movement.Static)
        self.grid.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid.setUniformItemSizes(True)
        self.grid.setGridSize(QSize(76, 42))
        self.grid.currentItemChanged.connect(self._selection_changed)
        self.grid.itemActivated.connect(self._open_device)
        layout.addWidget(self.grid, 1)
        layout.addWidget(QLabel("Chaque case affiche le dernier nombre de l’IPv4. "
                                "●  Appareil observé     ·  Sans observation"))

        footer = QHBoxLayout()
        self.details = QLabel()
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        footer.addWidget(self.details, 1)
        self.open_button = QPushButton("Voir dans l’inventaire")
        self.open_button.clicked.connect(lambda: self._open_device(self.grid.currentItem()))
        self.open_button.setEnabled(False)
        footer.addWidget(self.open_button)
        layout.addLayout(footer)

    def set_plan(self, plan: Plan):
        self.observed.clear()
        self.cells.clear()
        self.grid.clear()
        self._selection_changed(None)
        self.segment.setText(f"{plan.adapter.name}   ·   IP locale {plan.adapter.address.ip}")
        for ip in plan.targets:
            item = QListWidgetItem(f"·  {ip.packed[-1]}")
            item.setData(Qt.ItemDataRole.UserRole, ip)
            item.setSizeHint(QSize(72, 38))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setBackground(QColor("#edf1f3"))
            item.setForeground(QColor("#344854"))
            label = f"{ip} · Sans observation"
            item.setToolTip(label)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, label)
            self.grid.addItem(item)
            self.cells[ip] = item

    @Slot(object)
    def observe(self, device: Device):
        item = self.cells.get(device.ip)
        if item is None:
            return
        self.observed[device.ip] = device
        item.setText(f"●  {device.ip.packed[-1]}")
        item.setForeground(QColor("#07594e"))
        item.setBackground(QColor("#cceee5"))
        label = f"{device.ip} · Appareil observé · {device.method}"
        item.setToolTip(label)
        item.setData(Qt.ItemDataRole.AccessibleTextRole, label)
        if item is self.grid.currentItem():
            self._selection_changed(item)

    def _selection_changed(self, item, previous=None):
        if item is None:
            self.details.clear()
            self.open_button.setEnabled(False)
            return
        ip = item.data(Qt.ItemDataRole.UserRole)
        device = self.observed.get(ip)
        self.open_button.setEnabled(device is not None)
        fields = [str(ip)]
        if device:
            fields.extend(filter(None, (device.hostname, device.mac, device.vendor, device.method)))
        else:
            fields.append("Aucune observation enregistrée pour cette adresse.")
        self.details.setText("   ·   ".join(fields))

    def _open_device(self, item):
        if item is not None:
            ip = item.data(Qt.ItemDataRole.UserRole)
            if ip in self.observed:
                self.device_requested.emit(ip)
