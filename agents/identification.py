"""Enrichit uniquement un hôte positivement observé. Auteur : Onlyrutsuu."""
from dataclasses import replace

from core.models import Device, PortResult
from core.scope import Session, StopScan, TargetDenied
from skills.dns import skill_dns_resolve
from skills.journal import RunIssues
from skills.oui import skill_oui_lookup
from skills.tcp import skill_tcp_probe


def identify(session: Session, device: Device, registry: dict[str, str], issues: RunIssues) -> Device:
    host = replace(device, vendor=skill_oui_lookup(device.mac, registry))
    ports = []
    try:
        if session.plan.dns_enabled and issues.available("DNS"):
            try:
                host = replace(host, hostname=skill_dns_resolve(session, host.ip))
            except OSError as exc:
                issues.error("DNS", exc)
            except TargetDenied as exc:
                issues.note(f"DNS:{exc}", str(exc))
        for port in session.plan.ports:
            session.stop_if_needed()
            if not issues.available("TCP"):
                ports.append(PortResult(port, "error"))
                continue
            try:
                ports.append(skill_tcp_probe(session, host.ip, port))
            except OSError as exc:
                issues.error("TCP", exc)
                ports.append(PortResult(port, "error"))
    except StopScan:
        pass  # Une observation acquise survit à l’annulation de son enrichissement.
    except TargetDenied as exc:
        issues.note(str(exc), str(exc))
    return replace(host, ports=tuple(ports))
