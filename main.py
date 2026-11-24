"""Point d’entrée RUX. Auteur : Onlyrutsuu."""
import argparse
import json
import os
import platform
import sys
import tempfile
import traceback
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="RUX · inventaire local par Onlyrutsuu")
    parser.add_argument("--self-test", type=Path, metavar="RAPPORT",
                        help="Vérifier le démarrage, Qt, SQLite et le registre hors ligne.")
    args = parser.parse_args()
    from PySide6 import __version__ as pyside_version
    from PySide6.QtCore import QTimer, qVersion
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from core import config
    from core.inventory import Inventory
    from core.windows_net import WindowsNet
    from gui.main_window import MainWindow
    from gui.style import apply_style
    from skills.oui import load_registry

    app = QApplication([sys.argv[0]])
    app.setApplicationName(config.APP)
    app.setOrganizationName(config.AUTHOR)
    app.setApplicationVersion(config.VERSION)
    app.setWindowIcon(QIcon(str(config.DATA / "rux.ico")))
    apply_style(app)
    backend = None
    init_error = None
    if os.name == "nt":
        try:
            backend = WindowsNet()
        except (AttributeError, OSError) as exc:
            init_error = str(exc)
    if args.self_test:
        result = {"application": config.APP, "author": config.AUTHOR, "version": config.VERSION,
                  "platform": platform.platform(), "python": platform.python_version(),
                  "qt": qVersion(), "pyside": pyside_version, "ok": False}
        try:
            if os.name == "nt" and backend is None:
                raise RuntimeError(init_error or "API Windows indisponibles.")
            result["interfaces"] = len(backend.adapters()) if backend else None
            result["oui_prefixes"] = len(load_registry())
            if result["oui_prefixes"] < 1000 or app.windowIcon().isNull():
                raise RuntimeError("Ressources embarquées incomplètes.")
            with tempfile.TemporaryDirectory(prefix="rux-test-") as tmp:
                Inventory(Path(tmp) / "test.sqlite3").close()
                window = MainWindow(backend, Path(tmp))
                window.show()
                QTimer.singleShot(80, window.close)
                result["ok"] = app.exec() == 0
        except Exception:
            result["error"] = traceback.format_exc()
        args.self_test.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if result["ok"] else 1

    window = MainWindow(backend, config.user_dir())
    if init_error:
        QMessageBox.warning(window, "API Windows indisponibles", init_error)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
