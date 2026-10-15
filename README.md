# Automatisk fordeling av salgsmuligheter

Dette prosjektet viser hvordan en kunngjøring kan bli til en oppgave hos riktig selger eller partneransvarlig. Målet er å redusere manuell fordeling.

**Alt du ser i demoen er oppdiktet.** Ingen oppgaver eller varsler blir sendt.

## Slik prøver du demoen første gang

**Dette er et program du kjører på din egen PC. Nettleserlenken virker først etter at programmet er startet.**

1. **Installer Python 3.11 eller nyere** hvis du ikke har det. Bruk [python.org](https://www.python.org/downloads/). Ingen API-nøkler eller ekstra Python-pakker trengs.
2. **[Last ned prosjektet som ZIP](https://github.com/G0KU-DOTCOM/automating-mission-distribution/archive/refs/heads/main.zip)** og pakk det ut. Åpne mappen som inneholder `README.md`, `demo_data` og `mission_distribution`. Ikke kjør fra selve ZIP-filen.
3. **Åpne en terminal i denne mappen**, og følg oppskriften for din PC nedenfor. Kjør én linje om gangen. Versjonskommandoen må vise Python 3.11 eller nyere.

<details>
<summary><strong>Mac / Linux – vis kommandoene</strong></summary>

På Mac: Åpne Terminal, skriv `cd ` med et mellomrom etterpå, dra den utpakkede prosjektmappen inn i terminalvinduet og trykk Enter. På Linux bruker du `cd` til samme prosjektmappe.

```sh
python3 --version
python3 -m venv .venv
.venv/bin/python -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
.venv/bin/python -m mission_distribution serve --db runtime/fagdemo.sqlite3
```

</details>

<details>
<summary><strong>Windows – vis kommandoene for PowerShell</strong></summary>

Åpne PowerShell og bruk `cd` til den utpakkede prosjektmappen. Sett anførselstegn rundt mappebanen hvis den inneholder mellomrom.

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
.\.venv\Scripts\python.exe -m mission_distribution serve --db runtime/fagdemo.sqlite3
```

Hvis `py` ikke finnes, prøv `python` i de to første linjene. Kontroller at versjonen er 3.11 eller nyere før du fortsetter.

</details>

Kommandoene lager prosjektets eget Python-miljø, leser inn de oppdiktede oppdragene og starter nettsiden lokalt. Du trenger ikke aktivere miljøet separat; kommandoene bruker riktig Python direkte.

**Du trenger ikke `requirements.txt` eller `pip install` i denne versjonen.** Programmet bruker bare det som følger med Python. Vi legger til en avhengighetsfil når prosjektet faktisk trenger eksterne pakker.

4. **Vent til terminalen viser `Oppdragsoversikt: http://127.0.0.1:8765`.** Åpne deretter [demoen i nettleseren](http://127.0.0.1:8765/). La terminalen stå åpen mens du bruker den. Stopp med **Ctrl+C**.

Du skal nå se seks oppgaver i hver kanal og to bortsorterte konkurranser. Velg kanal og åpne et oppdrag for å se begrunnelsen, velge mottaker og godkjenne lokalt. Ingenting sendes til andre.

## Neste gang

Åpne terminalen i **samme prosjektmappe** og kjør bare startkommandoen:

- Mac / Linux: `.venv/bin/python -m mission_distribution serve`
- Windows PowerShell: `.\.venv\Scripts\python.exe -m mission_distribution serve`

Åpne nettleserlenken når adressen vises i terminalen. Tidligere mottakerbytter og godkjenninger ligger fortsatt lokalt. Du skal ikke lage miljøet eller lese inn eksempeldata på nytt ved hver oppstart.

Hvis en eldre demo kjører mens du oppdaterer koden, stopp den med Ctrl+C og start igjen. [Se feilsøking og en kort testgjennomgang](docs/nettleserdemo.md).

## Hva fungerer nå?

1. Programmet leser eksempeldata og samler poster som gjelder samme konkurranse.
2. Regler bruker fagkoder for anskaffelser (CPV), tittel og beskrivelse til å finne fag. Leveringssted brukes til å finne område.
3. Programmet foreslår mottaker: kundens registrerte selger først i direkte salg, ellers ansvarlig for fag og område. Partnerkanalen bruker sin egen ansvarsliste.
4. Resultatet lagres lokalt. Nye frister oppdaterer samme oppgave, og gjentatt innlesing lager ikke ekstra oppgaver.
5. Du kan velge mottaker og godkjenne lokalt. Nye opplysninger eller endret mottaker krever ny godkjenning.

Programmet forklarer hvilke regler som traff. Ukjent fag går videre til fordeling eller avklaring. Oppdrag uten relevante treff lagres med forklaring og får ingen nye oppgaver.

## Hva gjenstår?

Demoen har **ingen AI, brukerpålogging eller tilkobling til Doffin, Mercell, CRM eller Microsoft 365**. Den bruker en liten regeltabell som demonstrasjon, ikke arbeidsgiverens faktiske ansvarsdata. Den lokale brukeren kan lese begge kanaler; tilgangsstyring gjenstår.

Mottakerbytte og godkjenning virker lokalt, uten pålogging. Kapasitet og tidligere kundekontakt styrer foreløpig ikke fordelingen. Tilbakemeldinger og retting av fag, område og regeltabeller i nettleseren gjenstår. AI-modell skal velges sammen før den kobles til.

## Les mer hvis du trenger det

- [Fagvurdering med eksempler](docs/fagvurdering.md)
- [Oppdragsoversikt i nettleseren](docs/nettleserdemo.md)
- [Prøv duplikater, fristendring og manuell omfordeling](docs/innlesing.md)
- [Hva gjør filene?](docs/filer.md)
- [Valgene i demoen](docs/demovalg.md)
- [Planen videre](docs/utviklingsplan.md)

Kjør testene med `python3 -m unittest discover -s tests`.
