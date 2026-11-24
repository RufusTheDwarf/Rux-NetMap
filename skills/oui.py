"""Recherche locale du préfixe MAC le plus spécifique. Auteur : Onlyrutsuu."""
import csv
import re
from pathlib import Path

from core.config import DATA


def load_registry(path: Path = DATA / "oui.csv") -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {row["prefix"].upper(): row["organization"] for row in csv.DictReader(file)}


def skill_oui_lookup(mac: str | None, registry: dict[str, str]) -> str | None:
    """Cherche MA-S, MA-M puis MA-L. Les adresses locales restent inconnues."""
    raw = (mac or "").replace(":", "").replace("-", "").upper()
    if not re.fullmatch("[0-9A-F]{12}", raw) or int(raw[:2], 16) & 3 or int(raw, 16) == 0:
        return None
    for length in (9, 7, 6):
        if name := registry.get(raw[:length]):
            return name
    return None
