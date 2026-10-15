# Automatisk fordeling av salgsmuligheter

Dette prosjektet viser hvordan en kunngjøring kan bli til en oppgave hos riktig selger eller partneransvarlig. Målet er å redusere manuell fordeling.

**Alt du ser i demoen er oppdiktet.** Ingen oppgaver eller varsler blir sendt.

## Slik prøver du demoen første gang

**Dette er et program på din egen PC. Nettleserlenken virker først når programmet kjører.**

1. **Installer Python 3.11 eller nyere** fra [python.org](https://www.python.org/downloads/) hvis det mangler.
2. **[Last ned prosjektet som ZIP](https://github.com/G0KU-DOTCOM/automating-mission-distribution/archive/refs/heads/main.zip)** og pakk det ut.
3. **På Windows: dobbeltklikk `Start-demo.cmd`** i den utpakkede mappen. Den lager prosjektets miljø ved behov, leser inn oppdiktede oppdrag og starter demoen.
4. **Nettleseren åpnes når serveren er klar.** Hvis den ikke åpnes, bruk adressen som står i vinduet, normalt [http://127.0.0.1:8765](http://127.0.0.1:8765/). La oppstartsvinduet stå åpent. Stopp med **Ctrl+C** i dette vinduet.

Du skal se seks oppgaver i hver kanal og to bortsorterte konkurranser på en ny database. Åpne et oppdrag for å se begrunnelsen, velge mottaker og godkjenne lokalt. Ingenting sendes til andre.

**Du trenger ikke `requirements.txt`, API-nøkler eller `pip install`.** Programmet bruker bare det som følger med Python. Startfilen bruker miljøets Python direkte; du trenger ikke aktivere det selv.

<details>
<summary><strong>Mac / Linux</strong></summary>

Åpne en terminal i den utpakkede prosjektmappen, og kjør:

```sh
python3 start_demo.py
```

Python må være 3.11 eller nyere. På Mac kan du skrive `cd ` med et mellomrom, dra prosjektmappen inn i terminalen og trykke Enter for å komme til riktig mappe. Startprogrammet ordner miljø, eksempeldata og nettleser.

</details>

<details>
<summary><strong>Windows: starte manuelt fra PowerShell</strong></summary>

Åpne PowerShell og bruk `cd` til mappen som inneholder `README.md` og `mission_distribution`. Sett anførselstegn rundt mappebanen hvis den inneholder mellomrom. Kjør én linje om gangen:

```powershell
py -3 --version
py -3 -X utf8 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
.\.venv\Scripts\python.exe -X utf8 -m mission_distribution serve --db runtime/fagdemo.sqlite3
```

Versjonskommandoen må vise Python 3.11 eller nyere. Hvis `py` mangler, prøv `python` i de to første linjene. Åpne nettleseradressen når serveren har startet. Du trenger ikke kjøre et PowerShell-aktiveringsskript eller endre maskinens sikkerhetsinnstillinger.

</details>

## Neste gang

Dobbeltklikk **`Start-demo.cmd`** igjen på Windows. På Mac/Linux bruker du **`python3 start_demo.py`** igjen fra prosjektmappen. Tidligere mottakerbytter og godkjenninger beholdes; eksempelfilen lager ikke duplikater ved ny oppstart.

Startfilen må kjøres fra den utpakkede mappen, ikke inne i ZIP-filen. Hvis en eldre demo kjører mens du oppdaterer koden, stopp den med Ctrl+C og start igjen. [Se feilsøking og en kort testgjennomgang](docs/nettleserdemo.md).

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

Vil du kjøre testene selv? Bruk `py -3 -X utf8 -m unittest discover -s tests` på Windows eller `python3 -m unittest discover -s tests` på Mac/Linux fra prosjektmappen.
