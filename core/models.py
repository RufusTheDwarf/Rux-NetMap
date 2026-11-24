"""Modèles immuables partagés entre agents et interface. Auteur : Onlyrutsuu."""
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv4Interface, IPv4Network


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Adapter:
    index: int
    luid: int
    guid: str
    network_guid: str
    name: str
    address: IPv4Interface
    mac: str | None
    dns: tuple[IPv4Address, ...] = ()

    @property
    def history_key(self) -> str:
        return "|".join((self.guid.lower(), self.network_guid.lower(), str(self.address.network)))


@dataclass(frozen=True)
class Plan:
    adapter: Adapter
    network: IPv4Network
    targets: tuple[IPv4Address, ...]
    ports: tuple[int, ...]
    timeout_ms: int
    dns_enabled: bool
    dns_server: IPv4Address | None


@dataclass(frozen=True)
class PortResult:
    port: int
    state: str


@dataclass(frozen=True)
class Device:
    ip: IPv4Address
    mac: str | None
    method: str
    first_seen: str
    last_seen: str
    hostname: str | None = None
    vendor: str | None = None
    latency_ms: int | None = None
    ports: tuple[PortResult, ...] = ()


@dataclass(frozen=True)
class Snapshot:
    scan_id: str
    plan: Plan
    started: str
    ended: str
    status: str
    checked: int
    devices: tuple[Device, ...]
    notices: tuple[str, ...]
