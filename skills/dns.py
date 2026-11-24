"""PTR depuis le cache Windows ou un seul DNS local confirmé. Auteur : Onlyrutsuu."""
import re
import secrets
import socket
import struct
from ipaddress import IPv4Address

from core.scope import Session
from skills.tcp import bind_local

_LABEL = re.compile(rb"[A-Za-z0-9_-]{1,63}")


def _read_name(packet: bytes, offset: int) -> tuple[str, int]:
    """Décode un nom DNS compressé et renvoie l’offset du champ suivant."""
    labels = []
    visited = set()
    end = None
    length = 0
    while offset < len(packet) and offset not in visited and len(visited) < 128:
        visited.add(offset)
        size = packet[offset]
        if size == 0:
            return ".".join(labels), offset + 1 if end is None else end
        if size & 0xC0 == 0xC0:
            if offset + 1 >= len(packet):
                break
            if end is None:
                end = offset + 2
            offset = ((size & 0x3F) << 8) | packet[offset + 1]
            continue
        part = packet[offset + 1:offset + size + 1]
        length += size + 1
        if len(part) != size or not _LABEL.fullmatch(part) or length > 254:
            break
        labels.append(part.decode("ascii"))
        offset += size + 1
    raise ValueError("Nom DNS invalide ou pointeur cyclique.")


def _ptr_answer(packet: bytes, ident: int, query: str) -> str | None:
    """Accepte uniquement une réponse complète à notre question PTR exacte."""
    try:
        tid, flags, qd, an, _, _ = struct.unpack_from("!6H", packet)
        if tid != ident or flags & 0xFA0F != 0x8000 or qd != 1:
            return None
        name, offset = _read_name(packet, 12)
        if name.casefold() != query or struct.unpack_from("!HH", packet, offset) != (12, 1):
            return None
        offset += 4
        for _ in range(an):
            owner, offset = _read_name(packet, offset)
            kind, cls, _, size = struct.unpack_from("!HHIH", packet, offset)
            offset += 10
            end = offset + size
            if end > len(packet):
                return None
            if kind == 12 and cls == 1 and owner.casefold() == query:
                host, used = _read_name(packet, offset)
                if used == end and host:
                    return host
            offset = end
    except (ValueError, struct.error):
        pass
    return None


def skill_dns_resolve(session: Session, ip: IPv4Address) -> str | None:
    """Résout le PTR sans DNS public ni repli vers le résolveur système en ligne."""
    if not session.plan.dns_enabled:
        return None
    session.guard(ip)
    cached = session.backend.cached_ptr(ip)
    if cached or session.plan.dns_server is None:
        return cached
    server = session.plan.dns_server
    session.guard(server)
    ident = secrets.randbits(16)
    query = ip.reverse_pointer
    labels = b"".join(bytes([len(s)]) + s.encode("ascii") for s in query.split("."))
    packet = struct.pack("!6H", ident, 0, 1, 0, 0, 0) + labels + b"\0" + struct.pack("!HH", 12, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        bind_local(sock, session.plan.adapter, session.plan.timeout_ms)
        try:
            sock.connect((str(server), 53))
            sock.send(packet)
            return _ptr_answer(sock.recv(4096), ident, query)
        except (TimeoutError, ConnectionResetError, ConnectionRefusedError):
            return None
