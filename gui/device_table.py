"""Table Qt avec tri typé et filtrage sur toutes les colonnes. Auteur : Onlyrutsuu."""
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, Slot

from agents.report import device_record
from core.models import Device

COLUMNS = (("ip", "Adresse IP"), ("hostname", "Nom DNS"), ("mac", "Adresse MAC"),
           ("vendor", "Fabricant présumé"), ("method", "Détection"), ("ports", "Ports TCP"),
           ("first_seen", "Premier vu"), ("last_seen", "Dernier vu"))
PORT_LABELS = {"open": "ouvert", "refused": "refusé", "indeterminate": "indéterminé", "error": "erreur"}
DISPLAY = Qt.ItemDataRole.DisplayRole
SORT = Qt.ItemDataRole.UserRole


def local_date(value: str) -> str:
    return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M:%S")


class DeviceTable(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.tcp_requested = False

    def reset_scan(self, tcp_requested=False):
        self.beginResetModel()
        self.rows.clear()
        self.tcp_requested = tcp_requested
        self.endResetModel()

    @Slot(object)
    def add(self, device: Device):
        row = len(self.rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self.rows.append((device, device_record(device)))
        self.endInsertRows()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=DISPLAY):
        if role == DISPLAY and orientation == Qt.Orientation.Horizontal and 0 <= section < len(COLUMNS):
            return COLUMNS[section][1]
        return None

    def data(self, index, role=DISPLAY):
        if not index.isValid() or role not in (DISPLAY, SORT, Qt.ItemDataRole.ToolTipRole):
            return None
        device, row = self.rows[index.row()]
        key = COLUMNS[index.column()][0]
        value = row[key]
        if key == "ip" and role == SORT:
            return int(device.ip)
        if key in ("first_seen", "last_seen"):
            return value if role == SORT else local_date(value)
        if key == "ports":
            if not self.tcp_requested:
                return "Désactivé"
            if not value:
                return "Non testé"
            return ", ".join(f"{p['port']} {PORT_LABELS[p['state']]}" for p in value)
        if key == "vendor" and role == Qt.ItemDataRole.ToolTipRole:
            return "Titulaire du préfixe de la MAC. Une adresse locale peut masquer le fabricant."
        return str(value) if value is not None else "—"


class DeviceFilter(QSortFilterProxyModel):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setSourceModel(model)
        self.setSortRole(SORT)
        self.setFilterKeyColumn(-1)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setDynamicSortFilter(True)

    def lessThan(self, left, right):
        # PySide may expose IPv4 integers as different QVariant integral types.
        if left.column() == 0:
            return self.sourceModel().data(left, SORT) < self.sourceModel().data(right, SORT)
        return super().lessThan(left, right)
