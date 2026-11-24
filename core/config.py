"""Paramètres communs de RUX. Auteur : Onlyrutsuu."""
import os
from pathlib import Path

APP = "RUX"
AUTHOR = "Onlyrutsuu"
VERSION = "1.0.0"
MAX_ADDRESSES = 256
MAX_WORKERS = 8
TIMEOUT_MS = 650
MIN_TIMEOUT_MS = 100
MAX_TIMEOUT_MS = 3000
PORTS = (80, 443)
DATA = Path(__file__).resolve().parent.parent / "data"


def user_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / ".local" / "share") / APP
