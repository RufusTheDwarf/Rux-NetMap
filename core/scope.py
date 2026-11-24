"""Validation statique, consentement à usage unique et périmètre vivant. Auteur : Onlyrutsuu."""
from ipaddress import IPv4Address, IPv4Network, ip_network
from threading import Event, Lock
from typing import Protocol

from core import config
from core.models import Adapter, Plan

RFC1918 = tuple(IPv4Network(s) for s in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


class Backend(Protocol):
    def adapters(self) -> tuple[Adapter, ...]: ...
    def on_link(self, adapter: Adapter, ip: IPv4Address) -> bool: ...
    def arp(self, adapter: Adapter, ip: IPv4Address) -> str | None: ...
    def cached_mac(self, adapter: Adapter, ip: IPv4Address) -> str | None: ...
    def echo(self, adapter: Adapter, ip: IPv4Address, timeout_ms: int) -> int | None: ...
    def cached_ptr(self, ip: IPv4Address) -> str | None: ...


class ScopeError(ValueError):
    """Configuration proposée hors du périmètre."""


class StopScan(Exception):
    """Annulation ou perte de l’interface confirmée."""


class TargetDenied(Exception):
    """Aucun paquet autorisé vers cette destination."""


def private(ip: IPv4Address) -> bool:
    return any(ip in block for block in RFC1918)


def usable(ip: IPv4Address, network: IPv4Network) -> bool:
    return ip in network and (network.prefixlen >= 31 or ip not in
                              (network.network_address, network.broadcast_address))


def suggested(adapter: Adapter) -> IPv4Network:
    return IPv4Network((adapter.address.ip, max(24, adapter.address.network.prefixlen)), strict=False)


def plan_scan(adapter: Adapter, cidr: str, tcp: bool, dns: bool, timeout_ms: int) -> Plan:
    try:
        net = ip_network(cidr.strip(), strict=True)
    except ValueError as exc:
        raise ScopeError("Entre le CIDR exact du réseau, par exemple 192.168.1.0/24.") from exc
    if net.version != 4 or not any(net.subnet_of(block) for block in RFC1918):
        raise ScopeError("La plage entière doit appartenir à un bloc IPv4 privé RFC 1918.")
    if not private(adapter.address.ip) or not net.subnet_of(adapter.address.network):
        raise ScopeError("La plage dépasse le réseau directement connecté à cette interface.")
    if net.num_addresses > config.MAX_ADDRESSES:
        raise ScopeError(f"Choisis une plage de {config.MAX_ADDRESSES} adresses au maximum.")
    if not config.MIN_TIMEOUT_MS <= timeout_ms <= config.MAX_TIMEOUT_MS:
        raise ScopeError("Le délai doit être compris entre 100 et 3 000 ms.")
    targets = tuple(ip for ip in net.hosts() if usable(ip, adapter.address.network))
    if not targets:
        raise ScopeError("Cette plage ne contient aucune adresse hôte utilisable.")
    server = next((ip for ip in adapter.dns if ip in targets), None) if dns else None
    return Plan(adapter, net, targets, config.PORTS if tcp else (), timeout_ms, dns, server)


class Consent:
    """Le dialogue fournit un plan figé. Une seconde exécution exige un nouvel accord."""

    def __init__(self, plan: Plan, *, accepted: bool):
        if accepted is not True:
            raise PermissionError("Confirmation de l’utilisateur requise.")
        self._plan = plan
        self._used = False
        self._lock = Lock()

    def claim(self) -> Plan:
        with self._lock:
            if self._used:
                raise PermissionError("Cette confirmation a déjà servi.")
            self._used = True
        # Reconstruire la liste des cibles et les paramètres depuis les règles centrales.
        p = self._plan
        validated = plan_scan(p.adapter, str(p.network), bool(p.ports), p.dns_enabled, p.timeout_ms)
        if p != validated:
            raise ScopeError("Les paramètres ont changé depuis la confirmation.")
        return p


class Session:
    def __init__(self, plan: Plan, backend: Backend, cancel: Event):
        self.plan = plan
        self.backend = backend
        self.cancel = cancel
        self.allowed = frozenset(plan.targets)
        self.failure: str | None = None
        self._lock = Lock()

    def stop_if_needed(self) -> None:
        if self.cancel.is_set():
            raise StopScan(self.failure or "Annulation demandée.")

    def invalidate(self, reason: str) -> None:
        with self._lock:
            if self.failure is None:
                self.failure = reason
            self.cancel.set()

    def check_adapter(self) -> None:
        self.stop_if_needed()
        try:
            present = self.plan.adapter in self.backend.adapters()
        except OSError as exc:
            self.invalidate(f"Impossible de relire les interfaces Windows ({exc}).")
            raise StopScan(self.failure) from exc
        if not present:
            self.invalidate("L’interface ou sa configuration a changé. Confirme un nouveau scan.")
            raise StopScan(self.failure)

    def guard(self, ip: IPv4Address) -> None:
        if ip not in self.allowed:
            raise TargetDenied(f"{ip} se trouve hors de la plage confirmée.")
        self.check_adapter()
        try:
            direct = self.backend.on_link(self.plan.adapter, ip)
        except OSError as exc:
            raise TargetDenied(f"Route invérifiable vers {ip} ({exc}).") from exc
        if not direct:
            raise TargetDenied(f"{ip} ne possède pas de route directe sur l’interface choisie.")
        self.stop_if_needed()
