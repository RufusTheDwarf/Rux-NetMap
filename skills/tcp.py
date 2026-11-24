"""Connexions TCP bornées et socket attachée au LAN choisi. Auteur : Onlyrutsuu."""
import errno
import socket
import struct
from ipaddress import IPv4Address

from core.models import Adapter, PortResult
from core.scope import Session, TargetDenied


def bind_local(sock: socket.socket, adapter: Adapter, timeout_ms: int) -> None:
    sock.settimeout(timeout_ms / 1000)
    # Winsock asks for an interface index in network byte order.
    sock.setsockopt(socket.IPPROTO_IP, getattr(socket, "IP_UNICAST_IF", 31),
                    struct.pack("!I", adapter.index))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, 1)
    sock.bind((str(adapter.address.ip), 0))


def skill_tcp_probe(session: Session, ip: IPv4Address, port: int) -> PortResult:
    """Tente uniquement connect(), sans lire ni écrire de données applicatives."""
    if port not in session.plan.ports:
        raise TargetDenied("La vérification de ce port n’a pas été confirmée.")
    session.guard(ip)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        bind_local(sock, session.plan.adapter, session.plan.timeout_ms)
        try:
            sock.connect((str(ip), port))
            return PortResult(port, "open")
        except ConnectionRefusedError:
            return PortResult(port, "refused")
        except TimeoutError:
            return PortResult(port, "indeterminate")
        except OSError as exc:
            code = getattr(exc, "winerror", None) or exc.errno
            if code in (errno.ENETUNREACH, errno.EHOSTUNREACH, 10051, 10065):
                return PortResult(port, "indeterminate")
            raise
