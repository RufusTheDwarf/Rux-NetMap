"""Historique local par réseau et MAC. Auteur : Onlyrutsuu."""
import sqlite3
from dataclasses import replace
from pathlib import Path

from core.models import Adapter, Device


class Inventory:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=2)
        try:
            with self.db:
                self.db.execute("""CREATE TABLE IF NOT EXISTS devices (
                    network TEXT NOT NULL, mac TEXT NOT NULL,
                    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                    PRIMARY KEY (network, mac))""")
        except Exception:
            self.db.close()
            raise

    def remember(self, adapter: Adapter, device: Device) -> Device:
        if not device.mac:
            return device
        key = (adapter.history_key, device.mac)
        with self.db:
            self.db.execute("""INSERT INTO devices VALUES (?, ?, ?, ?)
                ON CONFLICT(network, mac) DO UPDATE SET
                first_seen = min(first_seen, excluded.first_seen),
                last_seen = max(last_seen, excluded.last_seen)""",
                (*key, device.first_seen, device.last_seen))
            first, last = self.db.execute(
                "SELECT first_seen, last_seen FROM devices WHERE network=? AND mac=?", key
            ).fetchone()
        return replace(device, first_seen=first, last_seen=last)

    def close(self) -> None:
        self.db.close()
