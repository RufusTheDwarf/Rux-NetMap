"""Projection stable des résultats pour la GUI et les exports. Auteur : Onlyrutsuu."""
from core import config
from core.models import Device, Snapshot
from skills.exports import skill_export_csv, skill_export_json


def device_record(device: Device) -> dict:
    return dict(ip=str(device.ip), mac=device.mac, hostname=device.hostname, vendor=device.vendor,
                method=device.method, latency_ms=device.latency_ms, first_seen=device.first_seen,
                last_seen=device.last_seen, ports=[dict(port=p.port, state=p.state) for p in device.ports])


def document(scan: Snapshot) -> dict:
    p = scan.plan
    return {
        "schema_version": 1, "application": {"name": config.APP, "version": config.VERSION,
                                             "author": config.AUTHOR},
        "scan": {"id": scan.scan_id, "status": scan.status, "started": scan.started,
                 "ended": scan.ended, "interface": p.adapter.name,
                 "source_ip": str(p.adapter.address.ip), "cidr": str(p.network),
                 "interface_cidr": str(p.adapter.address.network), "target_count": len(p.targets),
                 "checked": scan.checked, "observed": len(scan.devices), "ports": list(p.ports),
                 "timeout_ms": p.timeout_ms, "dns_enabled": p.dns_enabled,
                 "dns_server": str(p.dns_server) if p.dns_server else None,
                 "notices": list(scan.notices)},
        "devices": [device_record(d) for d in scan.devices],
    }


def export(scan: Snapshot, path, kind: str) -> int:
    writers = {"csv": skill_export_csv, "json": skill_export_json}
    return writers[kind](document(scan), path)
