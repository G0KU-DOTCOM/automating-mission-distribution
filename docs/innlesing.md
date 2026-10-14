# Prøv innlesing og oppdateringer

Alt i denne gjennomgangen er oppdiktet. Kildene er merket Doffin og Mercell for å vise flyten, men JSON-filene er vårt eget demoformat. Ingen eksterne API-er kalles.

Åpne en terminal i prosjektmappen. Python 3.11 eller nyere er nok.

## 1. Les inn første batch

En batch er en samling kildeposter som behandles sammen.

```sh
python3 -m mission_distribution ingest demo_data/source_batches/01-initial.json
```

Tre kildeposter blir til to konkurranser. Den første konkurransen finnes i begge demokildene. Opplysninger fra den ene fyller ut organisasjonsnummer og område som mangler i den andre.

Demoen foreslår én mottaker per konkurranse i hver kanal. Dermed opprettes fire lokale oppgaver. De er ikke levert til Planner.

## 2. Se oppgaven i direkte salg

```sh
python3 -m mission_distribution tasks --channel direkte --competition-ref DEMO-COMP-101
```

Du ser Demo Anna som kundeeier, tilbudsfrist 20. november 2026, begge kildereferansene og en oppgave-ID.

## 3. Bytt mottaker manuelt

```sh
python3 -m mission_distribution reassign --channel direkte --competition-ref DEMO-COMP-101 --person D-03
```

Demo Nora blir gjeldende mottaker i direkte salg. Dette registreres i oppgavens historikk. Partnerkanalens oppgave endres ikke.

## 4. Les inn fristendringen

```sh
python3 -m mission_distribution ingest demo_data/source_batches/02-update.json
```

Fristen endres til 27. november, og en ny dokumentlenke legges til. De samme oppgavene oppdateres. Det opprettes ingen nye.

Kjør visningen igjen:

```sh
python3 -m mission_distribution tasks --channel direkte --competition-ref DEMO-COMP-101
```

Oppgaven har samme ID, Demo Nora er fortsatt mottaker, og historikken viser fristendringen. Dokumentlenkene er bare lagret; filene er ikke lastet ned.

## 5. Prøv gjentatt innlesing

```sh
python3 -m mission_distribution ingest demo_data/source_batches/01-initial.json
```

Batchen er allerede behandlet. Antall oppgaver og gjeldende frist endres ikke. Den gamle fristen erstatter altså ikke den nye.

## 6. Prøv avlysning og usikkert duplikat

```sh
python3 -m mission_distribution ingest demo_data/source_batches/03-cancelled.json
python3 -m mission_distribution ingest demo_data/source_batches/04-possible-duplicate.json
python3 -m mission_distribution tasks --channel indirekte
```

Den andre konkurransens oppgave merkes som avlyst. Den siste kildeposten har lik innkjøper og tittel, men mangler felles referanse og har en annen frist. Den beholdes derfor separat med `MULIG_DUPLIKAT` for kontroll.

## Lagring og gjentakelse

Tilstanden lagres i `runtime/demo.sqlite3`. Filen følger ikke med til GitHub. Programmet husker innlesingene mellom kjøringene.

Hvis du ønsker en ny, separat demorunde, bruk samme nye databasebane på alle kommandoene, for eksempel `--db runtime/runde2.sqlite3`. En ny database begynner tom. Eksisterende demoer beholdes.

## Hvorfor oppdateringene er etterprøvbare

- Kilde-ID og konkurransereferanse brukes til å kjenne igjen eksisterende konkurranser.
- Hver kjent kildeversjon lagres, og feltene peker tilbake på kilden de kom fra.
- Eldre versjoner ignoreres. Like versjoner med motstridende innhold gir en feil som må avklares.
- Siste vellykkede lesegrense lagres per demokilde. Den flyttes først når hele batchen er lagret uten feil.
- En lagret mottaker beholdes ved oppdatering. Historikken er separat for hver kanal.

I en virkelig integrasjon må kildefelter, versjoner og hentemuligheter bekreftes mot API-ene. Demoen har ingen automatisk, timebasert API-henting eller brukerpålogging.
