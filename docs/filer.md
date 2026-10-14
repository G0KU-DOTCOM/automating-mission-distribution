# Hva gjør filene?

README forklarer hvordan du prøver demoen. Denne oversikten viser hvor hver del ligger.

| Fil | Hva den brukes til |
| --- | --- |
| `README.md` | Forklarer prosjektet og hva som er ferdig. |
| `.gitignore` | Forteller Git hvilke lokale filer som skal holdes utenfor repoet, blant annet vanlige nøkkelfiler og databaser. |
| `demo_data/opportunities.json` | De ti oppdiktede, klargjorte oppdragene. |
| `demo_data/direct_rules.json` | Oppdiktede selgere, kunder og ansvarsområder i direkte salg. |
| `demo_data/indirect_rules.json` | Partnerkanalens egen oppdiktede ansvarsliste. |
| `demo_data/source_batches/` | Fiktive kildeposter for innlesing, fristendring, avlysning, mulig duplikat og regelbasert fagvurdering. |
| `mission_distribution/models.py` | Leser data og stopper ugyldige ansvarslister. |
| `mission_distribution/routing.py` | Foreslår mottaker og forklarer hvilken regel som ble brukt. |
| `mission_distribution/classification.py` | Finner fag, relevans og område fra CPV-koder, tekst og en demotabell. |
| `demo_data/classification_rules.json` | De små eksempelreglene for fag og område. |
| `demo_data/classification_examples.json` | Åtte fiktive saker som viser treff, ukjent fag og bortsortering. |
| `tests/test_classification.py` | Kontrollerer fagvurderingen, inkludert viktige grensetilfeller. |
| `tests/test_classified_ingestion.py` | Kontrollerer at fagvurderingen virker sammen med innlesing og fordeling. |
| `mission_distribution/source_data.py` | Kontrollerer kildepostene i vårt eget demoformat. |
| `mission_distribution/ingestion.py` | Samler konkurranser og oppdaterer oppgaver med samme ID og eier. |
| `mission_distribution/storage.py` | Lagrer kildeposter, oppgaver og historikk i en lokal database. |
| `mission_distribution/workflow_cli.py` | Lar deg lese inn, se oppgaver og bytte mottaker fra terminalen. |
| `mission_distribution/__main__.py` | Lar deg kjøre demoen fra terminalen. |
| `tests/` | Kontrollerer at regler og eksempelsaker gir riktig resultat. |
| [Demovalg](docs/demovalg.md) | Forklarer forenklinger og valg vi har gjort selv. |
| [Innlesing steg for steg](docs/innlesing.md) | Viser hvordan du demonstrerer duplikatkontroll og oppdateringer. |
| [Utviklingsplan](docs/utviklingsplan.md) | Beskriver kravene vi bygger og kontrollerer steg for steg. |
