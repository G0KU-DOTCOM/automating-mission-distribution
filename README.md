# Automatisk fordeling av salgsmuligheter

Dette prosjektet viser hvordan en kunngjøring kan bli til en oppgave hos riktig selger eller partneransvarlig. Målet er å redusere manuell fordeling.

**Alt du ser i demoen er oppdiktet.** Ingen oppgaver eller varsler blir sendt.

## Åpne demoen i nettleseren

Du trenger Python 3.11 eller nyere. Åpne terminalen i prosjektmappen og aktiver prosjektets venv. Ingen ekstra pakker eller nøkler trengs.

```sh
python -m mission_distribution serve
```

Åpne **http://127.0.0.1:8765** i nettleseren. Velg kanal, søk i oppdragene og klikk på et oppdrag for å se begrunnelsen. Du kan også se mangler, kilder, historikk og bortsorterte konkurranser.

Oversikten bruker de lagrede dataene fra `runtime/fagdemo.sqlite3`. Har du fulgt demonstrasjonen tidligere, er de allerede klare. Er oversikten tom, bruk innlesingskommandoen under og oppdater siden.

La terminalen stå åpen mens du bruker demoen. Stopp med **Ctrl+C**. [Se den korte gjennomgangen](docs/nettleserdemo.md).

## Hva fungerer nå?

1. Programmet leser eksempeldata og samler poster som gjelder samme konkurranse.
2. Regler bruker fagkoder for anskaffelser (CPV), tittel og beskrivelse til å finne fag. Leveringssted brukes til å finne område.
3. Programmet foreslår mottaker: kundens registrerte selger først i direkte salg, ellers ansvarlig for fag og område. Partnerkanalen bruker sin egen ansvarsliste.
4. Resultatet lagres lokalt. Nye frister oppdaterer samme oppgave, og gjentatt innlesing lager ikke ekstra oppgaver.

Programmet forklarer hvilke regler som traff. Ukjent fag går videre til fordeling eller avklaring. Oppdrag uten relevante treff lagres med forklaring og får ingen nye oppgaver.

## Prøv hele kjeden

```sh
python3 -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
python3 -m mission_distribution tasks --channel direkte --db runtime/fagdemo.sqlite3
```

På en tom database blir ni kildeposter til åtte konkurranser. Seks konkurranser får én lokal oppgave i hver kanal, altså tolv oppgaver. To sorteres bort. Noen oppgaver krever avklaring og har derfor ingen mottaker ennå.

Bytt `direkte` til `indirekte` for å se partnerkanalens oppgaver. Kommandoen `assessments --db runtime/fagdemo.sqlite3` viser alle lagrede fagvurderinger, også de bortsorterte.

## Hva gjenstår?

Demoen har **ingen AI, brukerpålogging eller tilkobling til Doffin, Mercell, CRM eller Microsoft 365**. Den bruker en liten regeltabell som demonstrasjon, ikke arbeidsgiverens faktiske ansvarsdata. Den lokale brukeren kan lese begge kanaler; tilgangsstyring gjenstår.

Nettleseroversikten er en lesevisning. Kapasitet og tidligere kundekontakt styrer foreløpig ikke fordelingen. Godkjenning, tilbakemeldinger og redigering i nettleseren kommer senere. AI-modell skal velges sammen før den kobles til.

## Les mer hvis du trenger det

- [Fagvurdering med eksempler](docs/fagvurdering.md)
- [Oppdragsoversikt i nettleseren](docs/nettleserdemo.md)
- [Prøv duplikater, fristendring og manuell omfordeling](docs/innlesing.md)
- [Hva gjør filene?](docs/filer.md)
- [Valgene i demoen](docs/demovalg.md)
- [Planen videre](docs/utviklingsplan.md)

Kjør testene med `python3 -m unittest discover -s tests`.
