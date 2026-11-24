"""Disponibilité ICMPv4. Auteur : Onlyrutsuu."""
from ipaddress import IPv4Address

from core.scope import Session


def skill_icmp_ping(session: Session, ip: IPv4Address) -> int | None:
    """Renvoie la latence en ms, y compris zéro, ou None sans Echo Reply valide."""
    session.guard(ip)
    return session.backend.echo(session.plan.adapter, ip, session.plan.timeout_ms)
