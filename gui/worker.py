"""Thread du scan et signaux vers la boucle Qt. Auteur : Onlyrutsuu."""
from threading import Event

from PySide6.QtCore import QThread, Signal

from agents.orchestrator import run_scan


class ScanWorker(QThread):
    device = Signal(object)
    progress = Signal(int, int)
    result = Signal(object)
    failure = Signal(str)

    def __init__(self, consent, backend, directory, logger, parent=None):
        super().__init__(parent)
        self.consent = consent
        self.backend = backend
        self.directory = directory
        self.logger = logger
        self.cancel = Event()

    def run(self):
        try:
            snapshot = run_scan(self.consent, self.backend, self.cancel, self.directory,
                                self.logger, self.device.emit, self.progress.emit)
            self.result.emit(snapshot)
        except Exception as exc:
            self.logger.exception("Erreur du scan")
            self.failure.emit(str(exc))
