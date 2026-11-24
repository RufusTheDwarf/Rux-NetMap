"""Observations actives sur le segment confirmé. Auteur : Onlyrutsuu."""
from ipaddress import IPv4Address

from core.models import Device, utc_now
from core.scope import Session, TargetDenied
from skills.arp import skill_arp_scan
from skills.icmp import skill_icmp_ping
from skills.journal import RunIssues


def discover(session: Session, ip: IPv4Address, issues: RunIssues) -> Device | None:
    adapter = session.plan.adapter
    mac = None
    latency = None
    if ip == adapter.address.ip:
        if ip not in session.allowed:
            raise TargetDenied("Adresse locale en dehors de la plage confirmée.")
        session.check_adapter()
        method, mac = "local", adapter.mac
    else:
        if issues.available("ARP"):
            try:
                mac = skill_arp_scan(session, ip)
            except OSError as exc:
                issues.error("ARP", exc)
        if mac:
            method = "ARP"
        else:
            if issues.available("ICMP"):
                try:
                    latency = skill_icmp_ping(session, ip)
                except OSError as exc:
                    issues.error("ICMP", exc)
            if latency is None:
                return None
            method = "ICMP"
            if not session.cancel.is_set() and issues.available("Cache voisin"):
                try:
                    mac = session.backend.cached_mac(adapter, ip)
                except OSError as exc:
                    issues.error("Cache voisin", exc)
    now = utc_now()
    return Device(ip, mac, method, now, now, latency_ms=latency)
