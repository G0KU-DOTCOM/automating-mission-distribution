"""Run a local administrator demonstration without calling external services."""

import argparse
import json
from pathlib import Path

from .models import Channel, DemoDataError, load_direct_rules, load_indirect_rules, load_opportunities
from .routing import route_direct, route_indirect


def main() -> None:
    parser = argparse.ArgumentParser(description="Fordelingsdemo med bare oppdiktede data. Ingen oppgaver sendes.")
    parser.add_argument("--channel", required=True, choices=[channel.value for channel in Channel])
    parser.add_argument("--scenario", help="Vis bare én eksempelsak, for eksempel DEMO-001.")
    parser.add_argument("--json", action="store_true", help="Vis forslagene i maskinlesbart JSON-format.")
    args = parser.parse_args()
    data_dir = Path(__file__).resolve().parent.parent / "demo_data"
    try:
        opportunities = load_opportunities(data_dir / "opportunities.json")
        if args.scenario:
            opportunities = [item for item in opportunities if item.id == args.scenario]
            if not opportunities:
                parser.error(f"Eksempelsaken {args.scenario} finnes ikke.")
        if args.channel == Channel.DIRECT.value:
            rules = load_direct_rules(data_dir / "direct_rules.json")
            decisions = [route_direct(item, rules) for item in opportunities]
        else:
            rules = load_indirect_rules(data_dir / "indirect_rules.json")
            decisions = [route_indirect(item, rules) for item in opportunities]
    except DemoDataError as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps({"synthetic": True, "external_services_called": False,
                          "channel": args.channel, "decisions": [item.to_dict() for item in decisions]},
                         ensure_ascii=False, indent=2))
        return
    print(f"LOKAL DEMO — oppdiktede data — {args.channel} kanal")
    print("Dette er forslag. Ingen oppgaver er levert eller godkjent.\n")
    for decision in decisions:
        owner = f"{decision.owner.name} ({decision.owner.id})" if decision.owner else "Manuell avklaring"
        print(f"{decision.opportunity_id}: {decision.title}")
        print(f"  Mottaker: {owner}")
        print(f"  Årsak: {decision.reason_code} — {decision.explanation}")
        if decision.flags:
            print(f"  Flagg: {', '.join(decision.flags)}")
        print()


if __name__ == "__main__":
    main()
