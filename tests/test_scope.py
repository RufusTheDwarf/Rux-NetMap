"""Tests des décisions de périmètre et du consentement. Auteur : Onlyrutsuu."""
import unittest
from dataclasses import replace
from ipaddress import IPv4Interface

from core.scope import Consent, ScopeError, StopScan, TargetDenied, plan_scan, suggested
from skills.arp import skill_arp_scan
from tests.fakes import ADAPTER, IP, make_session


class ScopeTests(unittest.TestCase):
    def test_refuses_non_rfc1918_and_routed_blocks(self):
        for cidr in ("8.8.8.8/32", "127.0.0.0/8", "169.254.0.1/32", "100.64.0.0/24",
                     "172.32.0.0/24", "192.168.43.0/24", "::1/128", "0.0.0.0/0"):
            with self.subTest(cidr=cidr), self.assertRaises(ScopeError):
                plan_scan(ADAPTER, cidr, False, True, 500)

    def test_malformed_unaligned_or_unusable(self):
        for cidr in ("192.168.42.1/24", "example.org", "192.168.42.255/32", "192.168.42.0/32"):
            with self.subTest(cidr=cidr), self.assertRaises(ScopeError):
                plan_scan(ADAPTER, cidr, False, False, 500)

    def test_all_three_blocks_and_31_32(self):
        for ip in ("10.8.0.4", "172.31.255.8", "192.168.42.18"):
            a = replace(ADAPTER, address=IPv4Interface(ip + "/31"))
            plan = plan_scan(a, str(a.address.network), False, False, 100)
            self.assertEqual(len(plan.targets), 2)
            self.assertEqual(plan_scan(a, ip + "/32", False, False, 3000).targets, (IP(ip),))

    def test_large_network_shows_real_prefix_and_suggests_subset(self):
        a = replace(ADAPTER, address=IPv4Interface("10.30.45.6/16"))
        self.assertEqual(str(suggested(a)), "10.30.45.0/24")
        with self.assertRaises(ScopeError):
            plan_scan(a, "10.30.0.0/16", False, False, 500)
        self.assertEqual(len(plan_scan(a, str(suggested(a)), False, False, 500).targets), 254)

    def test_timeout_bounds(self):
        for value in (0, 99, 3001):
            with self.assertRaises(ScopeError):
                plan_scan(ADAPTER, "192.168.42.4/32", False, False, value)

    def test_dns_outside_confirmed_slice_or_public_is_ignored(self):
        a = replace(ADAPTER, dns=(IP("8.8.8.8"), IP("192.168.42.100")))
        self.assertIsNone(plan_scan(a, "192.168.42.0/29", False, True, 300).dns_server)

    def test_consent_is_positive_single_use_and_immutable(self):
        s = make_session()
        with self.assertRaises(PermissionError):
            Consent(s.plan, accepted=False)
        c = Consent(s.plan, accepted=True)
        self.assertEqual(c.claim(), s.plan)
        with self.assertRaises(PermissionError):
            c.claim()
        changed = replace(s.plan, targets=(IP("203.0.113.5"),))
        with self.assertRaises(ScopeError):
            Consent(changed, accepted=True).claim()

    def test_route_and_membership_are_checked_before_network_io(self):
        s = make_session()
        s.backend.indirect.add(IP("192.168.42.3"))
        for ip in ("8.8.8.8", "192.168.42.3", "192.168.42.12"):
            with self.assertRaises(TargetDenied):
                skill_arp_scan(s, IP(ip))
        self.assertFalse(s.backend.calls)

    def test_adapter_change_and_cancellation_block_traffic(self):
        for state in ("removed", "renumbered", "cancelled"):
            s = make_session()
            if state == "removed":
                s.backend.interfaces = ()
            elif state == "renumbered":
                s.backend.interfaces = (replace(ADAPTER, luid=ADAPTER.luid + 1),)
            else:
                s.cancel.set()
            with self.assertRaises(StopScan):
                skill_arp_scan(s, IP("192.168.42.2"))
            self.assertFalse(s.backend.calls)
