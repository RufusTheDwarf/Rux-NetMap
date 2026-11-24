"""Journal GUI et fichiers tournants. Auteur : Onlyrutsuu."""
import logging
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock


class _ViewHandler(logging.Handler):
    def __init__(self, show: Callable[[str], None]):
        super().__init__()
        self.show = show

    def emit(self, record: logging.LogRecord):
        self.show(self.format(record))


def open_journal(directory: Path, show: Callable[[str], None]) -> logging.Logger:
    logger = logging.Logger("rux", logging.INFO)
    formatter = logging.Formatter("%(asctime)sZ  %(levelname)s  %(message)s", "%Y-%m-%dT%H:%M:%S")
    formatter.converter = time.gmtime
    view = _ViewHandler(show)
    view.setFormatter(formatter)
    logger.addHandler(view)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(directory / "rux.log", maxBytes=1_048_576,
                                      backupCount=3, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except OSError as exc:
        logger.warning("Journal sur disque indisponible (%s).", exc)
    return logger


def skill_logging(logger: logging.Logger, level: int, scan_id: str, message: str) -> None:
    """Diffuse un événement horodaté au journal et à la vue configurée."""
    logger.log(level, "[%s] %s", scan_id, " ".join(str(message).splitlines()))


class RunIssues:
    """Un avertissement par cause et désactivation d’une méthode sans permission."""
    def __init__(self, logger: logging.Logger, scan_id: str):
        self.logger = logger
        self.scan_id = scan_id
        self._lock = Lock()
        self._notes: dict[str, str] = {}
        self._disabled: set[str] = set()

    def available(self, method: str) -> bool:
        with self._lock:
            return method not in self._disabled

    def note(self, key: str, message: str):
        with self._lock:
            if key in self._notes:
                return
            self._notes[key] = message
        skill_logging(self.logger, logging.WARNING, self.scan_id, message)

    def error(self, method: str, exc: OSError):
        code = getattr(exc, "winerror", None) or exc.errno
        if isinstance(exc, PermissionError) or code in (5, 13, 1314, 10013):
            with self._lock:
                self._disabled.add(method)
            self.note(method, f"{method} indisponible (permission refusée).")
        else:
            self.note(f"{method}:{code}", f"{method} : {exc}")

    def messages(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._notes.values())
