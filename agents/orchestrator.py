"""Cycle de vie d’un scan confirmé, avec un seul pool borné. Auteur : Onlyrutsuu."""
import logging
import sqlite3
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from threading import Event
from uuid import uuid4

from agents.discovery import discover
from agents.identification import identify
from core import config
from core.inventory import Inventory
from core.models import Device, Snapshot, utc_now
from core.scope import Backend, Consent, Session, StopScan, TargetDenied
from skills.journal import RunIssues, skill_logging
from skills.oui import load_registry


def run_scan(consent: Consent, backend: Backend, cancel: Event, directory: Path,
             logger: logging.Logger, seen: Callable[[Device], None],
             progress: Callable[[int, int], None]) -> Snapshot:
    plan = consent.claim()
    session = Session(plan, backend, cancel)
    scan_id, started = uuid4().hex, utc_now()
    notes = RunIssues(logger, scan_id)
    hosts: list[Device] = []
    checked = 0
    history = None
    try:
        session.check_adapter()
        skill_logging(logger, logging.INFO, scan_id,
                      f"Scan confirmé sur {plan.adapter.name}, {plan.network} "
                      f"({len(plan.targets)} cibles, TCP {plan.ports or 'désactivé'}).")
        try:
            history = Inventory(directory / "inventory.sqlite3")
        except (OSError, sqlite3.Error) as exc:
            notes.note("history", f"Historique indisponible. Résultats de session conservés ({exc}).")
        try:
            registry = load_registry()
        except (OSError, ValueError, KeyError) as exc:
            registry = {}
            notes.note("oui", f"Registre des fabricants indisponible ({exc}).")

        def probe(ip):
            host = discover(session, ip, notes)
            return identify(session, host, registry, notes) if host else None

        targets = iter(plan.targets)
        with ThreadPoolExecutor(max_workers=config.MAX_WORKERS, thread_name_prefix="RUX") as pool:
            pending = set()
            exhausted = False
            while True:
                while not cancel.is_set() and not exhausted and len(pending) < config.MAX_WORKERS:
                    ip = next(targets, None)
                    if ip is None:
                        exhausted = True
                    else:
                        pending.add(pool.submit(probe, ip))
                if not pending:
                    break
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for task in done:
                    try:
                        host = task.result()
                    except StopScan:
                        continue
                    except TargetDenied as exc:
                        notes.note(str(exc), str(exc))
                        host = None
                    except Exception as exc:
                        # Halt additional scheduling but still collect completed observations.
                        logger.exception("[%s] Échec du worker", scan_id)
                        session.invalidate(f"Échec du scan ({type(exc).__name__} : {exc}).")
                        continue
                    checked += 1
                    if host:
                        if history is not None:
                            try:
                                host = history.remember(plan.adapter, host)
                            except (OSError, sqlite3.Error) as exc:
                                notes.note("history", f"Écriture de l’historique impossible ({exc}).")
                                history.close()
                                history = None
                        hosts.append(host)
                        seen(host)
                    progress(checked, len(plan.targets))
    except StopScan:
        pass
    finally:
        if history is not None:
            history.close()

    if session.failure:
        notes.note("interruption", session.failure)
        status = "partial" if checked else "failed"
    elif cancel.is_set():
        status = "cancelled"
    elif notes.messages():
        status = "partial"
    else:
        status = "completed"
    skill_logging(logger, logging.INFO, scan_id,
                  f"Fin ({status}). {checked}/{len(plan.targets)} adresses traitées, "
                  f"{len(hosts)} appareils observés.")
    return Snapshot(scan_id, plan, started, utc_now(), status, checked,
                    tuple(sorted(hosts, key=lambda h: int(h.ip))), notes.messages())
