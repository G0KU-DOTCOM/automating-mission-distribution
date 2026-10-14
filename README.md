# Automatisk fordeling av salgsmuligheter

Dette prosjektet skal vise hvordan kunngjøringer fra Doffin og Mercell kan bli til oppgaver hos riktig selger eller partneransvarlig.

Målet er å redusere manuell fordeling og gjøre det tydelig hvem som har ansvar for å følge opp.

## Status nå

Første del virker nå: Programmet leser åtte oppdiktede oppdrag og foreslår en ansvarlig person, eller manuell avklaring, med en begrunnelse.

Fag og område er satt på forhånd i eksempeldataene. Det er ingen AI eller tilkobling til Doffin, Mercell, et kundesystem (CRM) eller Microsoft 365 ennå. Grensesnitt, godkjenning, duplikatkontroll og oppdatering av oppgaver kommer i senere steg.

## Prøv demoen

Du trenger Python 3.11 eller nyere. Åpne en terminal i prosjektmappen. Ingen ekstra Python-pakker eller API-nøkler er nødvendig.

Se forslagene for direkte salg:

```sh
python3 -m mission_distribution --channel direkte
```

Se forslagene for partnerkanalen:

```sh
python3 -m mission_distribution --channel indirekte
```

Se bare eksemplet der kunden har en selger, men faget er ukjent:

```sh
python3 -m mission_distribution --channel direkte --scenario DEMO-002
```

Dette er en lokal demonstrasjon for den som har tilgang til prosjektmappen. Den har ikke brukerpålogging. Ingen oppgaver blir sendt eller godkjent.

## Slik skal det fungere

1. **Les inn oppdrag.** Demoen starter med oppdiktede kunngjøringer. Tilkobling til datakildene kommer senere.
2. **Samle informasjonen.** Samme konkurranse skal behandles som ett oppdrag. Nye opplysninger skal oppdatere det eksisterende oppdraget.
3. **Finn fag og område.** Programmet bruker regler til å forstå hva oppdraget gjelder og hvor det skal utføres. Vi skal undersøke om AI kan hjelpe med å tolke teksten.
4. **Finn ansvarlig person.** I direkte salg prioriteres kundens registrerte selger. Ellers brukes fag og område. I salg via partnere brukes en egen oversikt over partneransvarlige.
5. **Opprett en oppgave.** Mottakeren får oppdraget med en forklaring på hvorfor det ble tildelt. Hvis reglene ikke gir en sikker mottaker, sendes saken til manuell avklaring.
6. **Følg opp endringer.** Endret frist skal oppdatere samme oppgave. Mottakeren kan også melde fra om feil fag eller feil mottaker.

De to salgskanalene skal ha adskilte oppgaver og interne opplysninger. Ved oppstart skal forslag godkjennes før levering. Senere kan avklarte oppdrag sendes direkte til ansvarlig person, slik at en teamleder slipper å fordele hvert oppdrag videre.

## Et eksempel

En fiktiv kunde har en registrert selger og publiserer et serviceoppdrag. Selgeren får oppgaven i direkte salg. Partnerkanalen vurderer samme offentlige kunngjøring etter sine egne regler og tildeler den til sin partneransvarlige.

Hvis kunden endrer tilbudsfristen, oppdateres de eksisterende oppgavene.

## Microsoft 365

En mulig videreføring er å bruke SharePoint til ansvarslister og dokumenter, og Planner til oppgaver. Tilganger og integrasjoner må avklares og testes før dette kan tas i bruk.

## Filene så langt

| Fil | Hva den brukes til |
| --- | --- |
| `README.md` | Forklarer prosjektet og hva som er ferdig. |
| `.gitignore` | Forteller Git hvilke lokale filer som skal holdes utenfor repoet, blant annet vanlige nøkkelfiler og databaser. |
| `demo_data/opportunities.json` | De åtte oppdiktede, klargjorte oppdragene. |
| `demo_data/direct_rules.json` | Oppdiktede selgere, kunder og ansvarsområder i direkte salg. |
| `demo_data/indirect_rules.json` | Partnerkanalens egen oppdiktede ansvarsliste. |
| `mission_distribution/models.py` | Leser data og stopper ugyldige ansvarslister. |
| `mission_distribution/routing.py` | Foreslår mottaker og forklarer hvilken regel som ble brukt. |
| `mission_distribution/__main__.py` | Lar deg kjøre demoen fra terminalen. |
| `tests/` | Kontrollerer at regler og eksempelsaker gir riktig resultat. |
| [Demovalg](docs/demovalg.md) | Forklarer forenklinger og valg vi har gjort selv. |
| [Utviklingsplan](docs/utviklingsplan.md) | Beskriver kravene vi bygger og kontrollerer steg for steg. |

Kjør kontrollene med `python3 -m unittest discover -s tests -v`.
