"""Feuille de style du poste de travail RUX. Auteur : Onlyrutsuu."""
from PySide6.QtGui import QColor, QPalette

STYLE = """
QWidget { font-family: "Segoe UI", sans-serif; font-size: 10pt; color: #182938; }
QMainWindow, QStackedWidget { background: #f6f8fa; }
QFrame#rail { background: #142b3a; border: none; }
QLabel#brand { color: #f3fafc; font-size: 26pt; font-weight: 700; padding-left: 6px; }
QLabel#railCredit { color: #c2d7df; padding-left: 8px; }
QPushButton#nav { text-align: left; border: 0; background: transparent; color: #d1e2e7; padding: 10px; }
QPushButton#nav:checked { color: white; background: #315163; font-weight: 600; }
QPushButton#nav:hover { background: #284758; }
QLabel#pageTitle { font-size: 19pt; font-weight: 650; }
QLabel#sectionTitle { font-size: 14pt; font-weight: 600; }
QFrame#panel, QTableView, QPlainTextEdit { background: white; border: 1px solid #c7d4dc; border-radius: 4px; }
QPushButton, QComboBox, QLineEdit, QSpinBox { background: white; border: 1px solid #aebec9; border-radius: 4px; padding: 5px 8px; }
QPushButton:hover { background: #e9f1f3; }
QPushButton#primary { color: white; background: #00665e; border-color: #00665e; font-weight: 600; padding: 6px 14px; }
QPushButton#primary:hover { background: #00564e; }
QPushButton:disabled, QPushButton#primary:disabled { color: #63747c; background: #e1e7eb; border-color: #c9d3d8; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus { border: 2px solid #077b94; }
QPushButton#nav:focus { border: 1px solid #b2e7ed; }
QTableView { alternate-background-color: #f1f6f8; selection-background-color: #c4e4e3; selection-color: #143e45; }
QListWidget#addressGrid { background: white; border: 1px solid #c7d4dc; padding: 6px; }
QListWidget#addressGrid::item:selected { background: #18566b; color: white; }
QHeaderView::section { background: #e6edef; color: #344d5a; border: none; border-right: 1px solid #cfdbdf; padding: 7px 5px; }
QProgressBar { background: #dce6e8; border: none; border-radius: 2px; }
QProgressBar::chunk { background: #007a6d; border-radius: 2px; }
QPlainTextEdit { font-family: Consolas, monospace; }
QStatusBar { background: #e8eef1; }
"""


def apply_style(app):
    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in ((QPalette.ColorRole.Window, "#f6f8fa"), (QPalette.ColorRole.WindowText, "#182938"),
                        (QPalette.ColorRole.Base, "#ffffff"), (QPalette.ColorRole.Text, "#182938"),
                        (QPalette.ColorRole.Button, "#ffffff"), (QPalette.ColorRole.ButtonText, "#182938"),
                        (QPalette.ColorRole.Highlight, "#00665e"), (QPalette.ColorRole.HighlightedText, "#ffffff")):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
