"""Read source batches and inspect persistent local demo tasks."""

import argparse
import json
from pathlib import Path
import sqlite3

from .ingestion import ingest_batch
from .classification import classify, load_classification_cases, load_classification_rules
from .models import Channel, DemoDataError, load_direct_rules, load_indirect_rules
from .source_data import load_source_batch
from .storage import DemoStore


ROOT = Path(__file__).resolve().parent.parent
FIELDS = {"buyer_org_number": "organisasjonsnummer", "main_trade": "hovedfag", "area": "område",
          "deadline": "frist", "title": "tittel", "description": "beskrivelse",
          "document_urls": "dokumentlenker", "public_flags": "offentlige flagg",
          "other_trades": "øvrige fag", "buyer_name": "innkjøpers navn",
          "main_cpv": "hoved-CPV", "buyer_municipality": "innkjøpers kommune", "notice_kind": "kunngjøringstype"}


def _print_assessment(result: dict) -> None:
    labels = {"relevant": "relevant etter demoreglene", "fag_ukjent": "ukjent fag – går videre",
              "ikke_relevant": "bortsortert etter demoreglene"}
    print(f"  Vurdering: {labels[result['relevance']]}")
    print(f"  Fag: {result['main_trade'] or 'ukjent'}; øvrige fag: {', '.join(result['other_trades']) or 'ingen'}")
    print(f"  Type: {result['work_type']}; område: {result['area'] or 'ukjent'}")
    print(f"  Hvorfor: {result['explanation']}")
    for hit in result["hits"]:
        if hit["kind"] == "cpv":
            print(f"  Treff: CPV {hit['code']} → {hit['trade']} (regel {hit['matched_prefix']})")
        else:
            fields = ", ".join(FIELDS.get(field, field) for field in hit["fields"])
            print(f"  Treff: «{hit['phrase']}» → {hit['trade']} i {fields}")
    if result["broad_codes"]:
        print("  Brede CPV-koder: " + ", ".join(result["broad_codes"]))
    if result["excluded_codes"]:
        print("  CPV-koder som ikke gir fagtreff: " + ", ".join(result["excluded_codes"]))
    print(f"  Områdegrunnlag: {result['area_explanation']}")
    if result["public_flags"]:
        print("  Flagg: " + ", ".join(result["public_flags"]))


def _print_tasks(tasks: list[dict], channel: Channel) -> None:
    print(f"LOKALE DEMOOPPGAVER — {channel.value} kanal")
    print("Oppdiktede data. Ingen Planner-oppgaver eller varsler er sendt.\n")
    if not tasks:
        print("Ingen lagrede oppgaver i dette utvalget.")
    for task in tasks:
        public = task["public_opportunity"]
        print(f"{task['task_id']}: {task['title']}")
        print(f"  Konkurransereferanse: {task['competition_ref'] or 'ikke oppgitt'}")
        print(f"  Tilbudsfrist: {task['deadline'] or 'ukjent'}")
        print(f"  Tilstand: {task['lifecycle']} — ikke levert")
        owner = task["owner"]
        if owner:
            print(f"  Mottaker: {owner['name']} ({owner['id']})")
            print(f"  Kapasitet: {owner['capacity']} (demodata; ikke brukt i fordelingen)")
        else:
            print("  Mottaker: manuell avklaring")
        print(f"  Tildelingsgrunnlag: {task['reason_code']} — {task['explanation']}")
        if public.get("classification"):
            _print_assessment(public["classification"])
        if task["data_review_required"]:
            print("  Krever datakontroll. Gjeldende mottaker er ikke automatisk endret.")
        print("  Kilder: " + ", ".join(f"{item['source']}: {item['record_id']}" for item in public["source_refs"]))
        if public["missing_fields"]:
            print("  Mangler: " + ", ".join(FIELDS.get(field, field) for field in public["missing_fields"]))
        if public["conflicts"]:
            print("  Kildene er uenige om: " + ", ".join(FIELDS.get(field, field) for field in public["conflicts"]))
        if public["possible_duplicate_ids"]:
            print("  MULIG_DUPLIKAT: beholdt separat for kontroll.")
        for event in task["events"]:
            details, kind = event["details"], event["type"]
            if kind == "frist_endret":
                print(f"  Historikk: frist {details['previous']} → {details['current']}")
            elif kind == "manuelt_omfordelt":
                print(f"  Historikk: mottaker {details['previous_owner_id']} → {details['new_owner_id']}")
            elif kind == "avlyst":
                print("  Historikk: konkurransen er avlyst.")
            elif kind == "opplysninger_endret":
                print("  Historikk: endret " + ", ".join(FIELDS.get(field, field) for field in details["fields"]))
            elif kind == "fagvurdering_endret":
                print(f"  Historikk: fagvurdering {details['previous']} → {details['current']}")
        print()


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Vedvarende lokal demo med fiktive kildeposter.")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Les inn en batch med fiktive kildeposter.")
    ingest.add_argument("batch", type=Path)
    ingest.add_argument("--rules", type=Path, default=ROOT / "demo_data" / "classification_rules.json")
    assessment = commands.add_parser("classify", help="Forklar fag og område for fiktive eksempelsaker.")
    assessment.add_argument("examples", type=Path)
    assessment.add_argument("--rules", type=Path, default=ROOT / "demo_data" / "classification_rules.json")
    assessment.add_argument("--json", action="store_true")
    assessments = commands.add_parser("assessments", help="Vis lagrede offentlige fagvurderinger, også bortsorterte.")
    show = commands.add_parser("tasks", help="Vis lagrede oppgaver i én kanal.")
    show.add_argument("--channel", required=True, choices=[channel.value for channel in Channel])
    show.add_argument("--competition-ref")
    reassign = commands.add_parser("reassign", help="Bytt mottaker manuelt i én kanal.")
    reassign.add_argument("--channel", required=True, choices=[channel.value for channel in Channel])
    reassign.add_argument("--competition-ref", required=True)
    reassign.add_argument("--person", required=True)
    for command in (ingest, show, reassign, assessments):
        command.add_argument("--db", type=Path, default=ROOT / "runtime" / "demo.sqlite3")
        command.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "classify":
            rules = load_classification_rules(args.rules)
            cases = load_classification_cases(args.examples)
            results = [classify(case, rules) for case in cases]
            if args.json:
                print(json.dumps({"synthetic": True, "ai_used": False, "assessments": results}, ensure_ascii=False, indent=2))
            else:
                print("FAGVURDERING — oppdiktede data og demonstrasjonsregler. Ingen AI.\n")
                for case, result in zip(cases, results):
                    print(f"{case.id}: {case.title}")
                    _print_assessment(result)
                    print()
            return
        batch = load_source_batch(args.batch) if args.command == "ingest" else None
        with DemoStore(args.db) as store:
            if args.command == "ingest":
                direct = load_direct_rules(ROOT / "demo_data" / "direct_rules.json")
                indirect = load_indirect_rules(ROOT / "demo_data" / "indirect_rules.json")
                classification_rules = load_classification_rules(args.rules)
                result = ingest_batch(store, batch, direct, indirect, classification_rules)
                if args.json:
                    print(json.dumps({"synthetic": True, "external_services_called": False, "report": result},
                                     ensure_ascii=False, indent=2))
                else:
                    print(f"LOKAL INNLESING — {result['batch_id']} — bare fiktive kildeposter")
                    print(f"Kildeposter: {result['records_seen']}; nye konkurranser: {result['created_competitions']}")
                    print(f"Nye demooppgaver: {result['created_tasks']}; oppdaterte: {result['updated_tasks']}")
                    print(f"Uendrede/gjentatte poster: {result['duplicate_records']}; eldre versjoner ignorert: {result['stale_records']}")
                    print(f"Mulige duplikater beholdt separat: {result['possible_duplicates']}")
                    print(f"Berørte konkurranser uten relevante treff: {result['not_relevant_competitions']}")
                    if result["already_processed"]:
                        print("Denne batchen er allerede behandlet. Ingen oppgaver er endret.")
                    print("Ingen eksterne API-er er kalt, og ingenting er levert til Microsoft 365.")
            elif args.command == "tasks":
                channel = Channel(args.channel)
                tasks = store.tasks(channel)
                if args.competition_ref:
                    tasks = [task for task in tasks if task["competition_ref"] == args.competition_ref]
                if args.json:
                    print(json.dumps({"synthetic": True, "channel": channel.value, "tasks": tasks},
                                     ensure_ascii=False, indent=2))
                else:
                    _print_tasks(tasks, channel)
            elif args.command == "assessments":
                results = store.assessments()
                if args.json:
                    print(json.dumps({"synthetic": True, "assessments": results}, ensure_ascii=False, indent=2))
                else:
                    print("LAGREDE OFFENTLIGE FAGVURDERINGER — ingen interne tildelinger.\n")
                    if not results:
                        print("Ingen lagrede fagvurderinger. De eldre klargjorte eksemplene bruker ikke fagvurdering.")
                    for result in results:
                        print(f"{result['competition_ref'] or 'Uten referanse'}: {result['title']}")
                        _print_assessment(result["classification"])
                        if result["conflicting_fields"]:
                            print("  Konflikt krever avklaring: " + ", ".join(result["conflicting_fields"]))
                        print()
            else:
                channel = Channel(args.channel)
                loader = load_direct_rules if channel == Channel.DIRECT else load_indirect_rules
                filename = "direct_rules.json" if channel == Channel.DIRECT else "indirect_rules.json"
                rules = loader(ROOT / "demo_data" / filename)
                person = rules.people.get(args.person)
                if person is None:
                    raise DemoDataError("Personen finnes ikke i den valgte kanalens ansvarsliste.")
                task_id = store.task_for_reference(args.competition_ref, channel)
                task = store.reassign(task_id, channel, person)
                if args.json:
                    print(json.dumps({"synthetic": True, "task": task}, ensure_ascii=False, indent=2))
                else:
                    print(f"Demooppgave {task_id}: mottaker er nå {person.name} ({person.id}).")
                    print("Oppgaven er fortsatt et forslag. Ingen godkjenning, levering eller varsel er sendt.")
    except (DemoDataError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
