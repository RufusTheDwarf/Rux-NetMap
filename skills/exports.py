"""Exports atomiques UTF-8. Auteur : Onlyrutsuu."""
import csv
import json
import os
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile


@contextmanager
def _output(path: Path, encoding: str):
    path = Path(path)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", dir=path.parent, prefix=".rux-", delete=False,
                                encoding=encoding, newline="") as file:
            temporary = Path(file.name)
            yield file
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _cell(value):
    if isinstance(value, str) and (value.startswith(("\t", "\n", "\r")) or
                                  value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def skill_export_json(report: dict, path: Path) -> int:
    """Écrit un document JSON UTF-8 et renvoie le nombre d’hôtes."""
    with _output(path, "utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    return len(report["devices"])


def skill_export_csv(report: dict, path: Path) -> int:
    """Écrit un résumé et une ligne par hôte. Séparateur ; et BOM pour Excel."""
    scan = report["scan"]
    columns = ("record_type", "scan_id", "status", "interface", "cidr", "started", "ended",
               "target_count", "checked", "observed", "requested_ports", "ip", "mac", "hostname",
               "vendor", "method", "latency_ms", "first_seen", "last_seen", "ports")
    summary = dict(scan_id=scan["id"], requested_ports=",".join(map(str, scan["ports"])))
    summary.update({k: scan[k] for k in ("status", "interface", "cidr", "started", "ended",
                                        "target_count", "checked", "observed")})
    with _output(path, "utf-8-sig") as file:
        writer = csv.DictWriter(file, columns, delimiter=";")
        writer.writeheader()
        writer.writerow({k: _cell(v) for k, v in dict(record_type="scan", **summary).items()})
        for device in report["devices"]:
            row = dict(summary, record_type="device", **device)
            row["ports"] = ", ".join(f"{p['port']}={p['state']}" for p in device["ports"])
            writer.writerow({k: _cell(v) for k, v in row.items()})
    return len(report["devices"])
