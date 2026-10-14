"""Explainable ownership proposals for one already prepared opportunity.

This module does not fetch notices, classify text, send tasks, or approve them.
Indirect routing receives only IndirectRules and cannot look up customers.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re

from .models import Channel, Coverage, DirectRules, IndirectRules, Person, PreparedOpportunity


@dataclass(frozen=True)
class Decision:
    opportunity_id: str
    title: str
    channel: Channel
    owner: Person | None
    reason_code: str
    explanation: str
    trade: str | None
    area: str | None
    flags: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "channel": self.channel.value,
            "status": "foreslått" if self.owner else "uavklart",
            "owner": {"id": self.owner.id, "name": self.owner.name} if self.owner else None,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "main_trade": self.trade,
            "area": self.area,
            "flags": list(self.flags),
            "delivery_status": "ikke_levert",
        }


def _decision(opportunity: PreparedOpportunity, channel: Channel, owner: Person | None,
              code: str, explanation: str, flags: tuple[str, ...]) -> Decision:
    return Decision(opportunity.id, opportunity.title, channel, owner, code, explanation,
                    opportunity.main_trade, opportunity.area, flags)


def _coverage_proposal(opportunity: PreparedOpportunity, channel: Channel,
                       coverage: dict[tuple[str, str], Coverage], people: dict[str, Person],
                       flags: tuple[str, ...]) -> Decision:
    if opportunity.main_trade is None:
        return _decision(opportunity, channel, None, "FAG_UKJENT",
                         "Hovedfaget er ukjent. Saken må avklares i denne kanalen.", flags)
    if opportunity.area is None:
        return _decision(opportunity, channel, None, "OMRÅDE_UKJENT",
                         "Området er ukjent. Saken må avklares i denne kanalen.", flags)
    rule = coverage.get((opportunity.main_trade, opportunity.area))
    if rule is None:
        return _decision(opportunity, channel, None, "INGEN_REGEL",
                         f"Ingen ansvarlig er registrert for {opportunity.main_trade} × {opportunity.area} i denne kanalen.", flags)
    owner = people[rule.owner_id]
    if owner.active:
        return _decision(opportunity, channel, owner, "FAG_OMRÅDE",
                         f"Ansvarlig for {rule.trade} × {rule.area} er aktiv.", flags)
    deputy = people.get(rule.deputy_id)
    if deputy and deputy.active:
        return _decision(opportunity, channel, deputy, "FAG_OMRÅDE_VIKAR",
                         f"Ansvarlig for {rule.trade} × {rule.area} er inaktiv. Aktiv stedfortreder er valgt.", flags)
    return _decision(opportunity, channel, None, "EIER_INAKTIV",
                     "Ansvarlig er inaktiv, og det finnes ingen aktiv stedfortreder i denne kanalen.", flags)


def _normal_name(name: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", name.casefold()).split())


def route_direct(opportunity: PreparedOpportunity, rules: DirectRules) -> Decision:
    channel, flags = Channel.DIRECT, opportunity.public_flags
    customer = rules.customers.get(opportunity.buyer_org_number)
    if customer:
        if customer.installed_base:
            flags += ("INSTALLERT_BASE",)
        if customer.owner_id:
            owner = rules.people[customer.owner_id]
            if owner.active:
                return _decision(opportunity, channel, owner, "KUNDEEIER",
                                 "Innkjøpers organisasjonsnummer har en aktiv kundeeier. Kundeeierskap prioriteres foran fag og område.", flags)
            if customer.deputy_id:
                deputy = rules.people[customer.deputy_id]
                if deputy.active:
                    return _decision(opportunity, channel, deputy, "KUNDEVIKAR",
                                     "Kundeeieren er inaktiv. Kundens aktive stedfortreder er valgt.", flags)
                return _decision(opportunity, channel, None, "EIER_INAKTIV",
                                 "Både kundeeier og registrert stedfortreder er inaktive. Saken må avklares.", flags)
            flags += ("EIER_INAKTIV",)
            proposal = _coverage_proposal(opportunity, channel, rules.coverage, rules.people, flags)
            return Decision(proposal.opportunity_id, proposal.title, proposal.channel,
                            proposal.owner, proposal.reason_code,
                            "Kundeeieren er inaktiv uten registrert stedfortreder. " + proposal.explanation,
                            proposal.trade, proposal.area, proposal.flags)
    else:
        # A conservative demo heuristic, not a confirmed employer rule or an AI probability.
        buyer = _normal_name(opportunity.buyer_name)
        for known in rules.customers.values():
            similarity = SequenceMatcher(None, buyer, _normal_name(known.name)).ratio()
            if similarity >= rules.name_similarity_threshold:
                return _decision(opportunity, channel, None, "MULIG_KUNDE",
                                 "Navnet ligner en registrert kunde uten bekreftet treff på organisasjonsnummer. Kundekoblingen må avklares.", flags)
    return _coverage_proposal(opportunity, channel, rules.coverage, rules.people, flags)


def route_indirect(opportunity: PreparedOpportunity, rules: IndirectRules) -> Decision:
    return _coverage_proposal(opportunity, Channel.INDIRECT, rules.coverage, rules.people,
                              opportunity.public_flags)
