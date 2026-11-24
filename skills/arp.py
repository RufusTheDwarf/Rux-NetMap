"""Résolution ARP active. Auteur : Onlyrutsuu."""
from ipaddress import IPv4Address

from core.scope import Session


def skill_arp_scan(session: Session, ip: IPv4Address) -> str | None:
    """Renvoie la MAC répondante sur le lien, ou None en l’absence de réponse."""
    session.guard(ip)
    return session.backend.arp(session.plan.adapter, ip)
