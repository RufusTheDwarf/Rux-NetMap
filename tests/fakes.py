"""Adaptateur mémoire : aucune sonde envoyée pendant les tests. Auteur : Onlyrutsuu."""
from ipaddress import IPv4Address, IPv4Interface
from threading import Event

from core.models import Adapter
from core.scope import Session, plan_scan

IP = IPv4Address
ADAPTER = Adapter(7, 987654321, "{lan-a}", "profile-a", "Ethernet test",
                  IPv4Interface("192.168.42.20/24"), "00:50:56:00:00:20", (IP("192.168.42.1"),))


class FakeNet:
    def __init__(self, adapter=ADAPTER):
        self.interfaces = (adapter,)
        self.indirect = set()
        self.macs = {}
        self.echoes = {}
        self.names = {}
        self.neighbors = {}
        self.calls = []

    def adapters(self):
        return self.interfaces

    def on_link(self, adapter, ip):
        return ip not in self.indirect

    def arp(self, adapter, ip):
        self.calls.append(("ARP", ip))
        return self.macs.get(ip)

    def echo(self, adapter, ip, timeout_ms):
        self.calls.append(("ICMP", ip))
        return self.echoes.get(ip)

    def cached_ptr(self, ip):
        self.calls.append(("DNS", ip))
        return self.names.get(ip)

    def cached_mac(self, adapter, ip):
        return self.neighbors.get(ip)


def make_session(cidr="192.168.42.0/29", tcp=False, dns=False):
    back = FakeNet()
    plan = plan_scan(ADAPTER, cidr, tcp, dns, 350)
    return Session(plan, back, Event())
