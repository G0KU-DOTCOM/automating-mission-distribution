"""Read our internal demo format and reject inconsistent responsibility data.

These files are not representations of the Doffin or Mercell API contracts.
Direct and indirect responsibilities are loaded from different files.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import json
from pathlib import Path
from typing import Any


class Channel(StrEnum):
    DIRECT = "direkte"
    INDIRECT = "indirekte"


TRADES = frozenset({"BA", "FS", "SE"})
PUBLIC_FLAGS = frozenset({"MERKENAVN", "TIDLIG_FASE", "KORT_FRIST", "FLERE_OMRÅDER", "MULIG_DUPLIKAT"})


class DemoDataError(ValueError):
    """Input cannot safely be used to make a routing decision."""


def _text(value: Any, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise DemoDataError(f"{field}: forventet tekst med innhold.")
    return value.strip()


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise DemoDataError(f"{field}: forventet true eller false.")
    return value


def _items(value: Any, field: str) -> list:
    if not isinstance(value, list):
        raise DemoDataError(f"{field}: forventet en liste.")
    return value


def _object(value: Any, field: str) -> dict:
    if not isinstance(value, dict):
        raise DemoDataError(f"{field}: forventet et objekt med felt og verdier.")
    return value


def _trade(value: Any, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or value not in TRADES:
        raise DemoDataError("fag: bruk BA, FS, SE eller null for ukjent hovedfag.")
    return value


def _org_number(value: Any, optional: bool = False) -> str | None:
    number = _text(value, "org_number", optional)
    if number is not None and (len(number) != 9 or not number.isascii() or not number.isdigit()):
        raise DemoDataError("org_number: forventet ni sifre, eller null hvis ukjent.")
    return number


def _read(path: Path) -> dict:
    try:
        value = _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DemoDataError(f"Kunne ikke lese gyldig JSON fra {path.name}.") from exc
    if value.get("synthetic") is not True:
        raise DemoDataError(f"{path.name}: demoen krever synthetic=true.")
    return value


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    channel: Channel
    active: bool


@dataclass(frozen=True)
class Coverage:
    trade: str
    area: str
    owner_id: str
    deputy_id: str | None


@dataclass(frozen=True)
class Customer:
    org_number: str
    name: str
    owner_id: str | None
    deputy_id: str | None
    installed_base: bool


@dataclass(frozen=True)
class PreparedOpportunity:
    id: str
    title: str
    buyer_name: str
    buyer_org_number: str | None
    main_trade: str | None
    other_trades: tuple[str, ...]
    area: str | None
    deadline: date | None
    public_flags: tuple[str, ...]


@dataclass(frozen=True)
class DirectRules:
    people: dict[str, Person]
    coverage: dict[tuple[str, str], Coverage]
    customers: dict[str, Customer]
    name_similarity_threshold: float


@dataclass(frozen=True)
class IndirectRules:
    people: dict[str, Person]
    coverage: dict[tuple[str, str], Coverage]


def _people(data: dict, channel: Channel) -> dict[str, Person]:
    people = {}
    for raw in _items(data.get("people"), "people"):
        row = _object(raw, "person")
        pid = _text(row.get("id"), "person.id")
        if pid in people:
            raise DemoDataError(f"Person-ID {pid} finnes flere ganger.")
        if row.get("channel") != channel.value:
            raise DemoDataError(f"Person {pid} tilhører ikke {channel.value} kanal.")
        people[pid] = Person(pid, _text(row.get("name"), "person.name"), channel,
                             _boolean(row.get("active"), "person.active"))
    return people


def _check_people(owner: str | None, deputy: str | None, people: dict[str, Person]) -> None:
    for pid in (owner, deputy):
        if pid is not None and pid not in people:
            raise DemoDataError(f"Ansvarlig/stedfortreder {pid} finnes ikke i kanalens personliste.")
    if owner is not None and owner == deputy:
        raise DemoDataError("Ansvarlig og stedfortreder må være forskjellige personer.")


def _coverage(data: dict, people: dict[str, Person]) -> dict[tuple[str, str], Coverage]:
    result = {}
    for raw in _items(data.get("coverage"), "coverage"):
        row = _object(raw, "coverage row")
        rule = Coverage(_trade(row.get("trade")), _text(row.get("area"), "area"),
                        _text(row.get("owner_id"), "owner_id"),
                        _text(row.get("deputy_id"), "deputy_id", True))
        key = (rule.trade, rule.area)
        if key in result:
            raise DemoDataError(f"Flere ansvarlige regler for {rule.trade} × {rule.area}.")
        _check_people(rule.owner_id, rule.deputy_id, people)
        result[key] = rule
    return result


def load_direct_rules(path: Path) -> DirectRules:
    data = _read(path)
    people = _people(data, Channel.DIRECT)
    coverage = _coverage(data, people)
    customers = {}
    for raw in _items(data.get("customers"), "customers"):
        row = _object(raw, "customer")
        customer = Customer(_org_number(row.get("org_number")),
                            _text(row.get("name"), "customer.name"),
                            _text(row.get("owner_id"), "owner_id", True),
                            _text(row.get("deputy_id"), "deputy_id", True),
                            _boolean(row.get("installed_base"), "installed_base"))
        if customer.org_number in customers:
            raise DemoDataError(f"Kunden {customer.org_number} finnes flere ganger.")
        _check_people(customer.owner_id, customer.deputy_id, people)
        customers[customer.org_number] = customer
    threshold = data.get("name_similarity_threshold")
    if type(threshold) not in (int, float) or not 0 < threshold <= 1:
        raise DemoDataError("name_similarity_threshold: forventet et tall over 0 og opptil 1.")
    return DirectRules(people, coverage, customers, threshold)


def load_indirect_rules(path: Path) -> IndirectRules:
    data = _read(path)
    # Refuse a combined file: partner routing must not load customer ownership.
    if "customers" in data:
        raise DemoDataError("Partnerfilen skal ikke inneholde kundeeierskap.")
    people = _people(data, Channel.INDIRECT)
    return IndirectRules(people, _coverage(data, people))


def load_opportunities(path: Path) -> list[PreparedOpportunity]:
    data = _read(path)
    result, ids = [], set()
    for raw in _items(data.get("opportunities"), "opportunities"):
        row = _object(raw, "opportunity")
        oid = _text(row.get("id"), "opportunity.id")
        if oid in ids:
            raise DemoDataError(f"Oppdrags-ID {oid} finnes flere ganger i demofilens klargjorte oppdrag.")
        main_trade = _trade(row.get("main_trade"), True)
        others = tuple(_trade(item) for item in _items(row.get("other_trades", []), "other_trades"))
        if len(set(others)) != len(others) or main_trade in others:
            raise DemoDataError(f"{oid}: faglisten inneholder duplikater.")
        flags = tuple(_text(item, "public_flag") for item in _items(row.get("public_flags", []), "public_flags"))
        if any(flag not in PUBLIC_FLAGS for flag in flags) or len(set(flags)) != len(flags):
            raise DemoDataError(f"{oid}: ugyldige eller dupliserte offentlige flagg.")
        raw_deadline = row.get("deadline")
        try:
            deadline = date.fromisoformat(_text(raw_deadline, "deadline")) if raw_deadline is not None else None
        except ValueError as exc:
            raise DemoDataError(f"{oid}: deadline må være en gyldig dato i formatet ÅÅÅÅ-MM-DD.") from exc
        result.append(PreparedOpportunity(
            oid, _text(row.get("title"), "title"), _text(row.get("buyer_name"), "buyer_name"),
            _org_number(row.get("buyer_org_number"), True), main_trade, others,
            _text(row.get("area"), "area", True), deadline, flags,
        ))
        ids.add(oid)
    return result
