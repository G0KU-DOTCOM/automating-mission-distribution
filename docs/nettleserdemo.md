# Oppdragsoversikten i nettleseren

Denne versjonen lar deg se og forstå resultatene uten å lese terminalutskrift. Det er en lokal lesevisning. Den godkjenner, endrer eller sender ingen oppgaver.

## Start

Åpne terminalen i prosjektmappen. Med prosjektets venv aktivert:

```sh
python -m mission_distribution serve
```

Åpne http://127.0.0.1:8765 i nettleseren. Terminalen må stå åpen. Stopp med Ctrl+C.

Visningen bruker `runtime/fagdemo.sqlite3`, altså den samme databasen som den siste innlesingsdemoen. Er den tom, åpne en annen terminal i prosjektmappen og les inn:

```sh
python -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
```

Oppdater nettsiden etterpå. Den leser lagrede data på nytt hver gang; den henter ikke noe fra Doffin eller Mercell.

## Prøv disse fire tingene

1. **Velg «Direkte salg».** Du ser bare denne kanalens mottakerforslag og historikk. Tallene øverst gjelder hele den valgte kanalen, også når du filtrerer listen.
2. **Åpne «Demo: tekniske arbeider».** Kundens selger Anna foreslås selv om faget er ukjent. Begrunnelsen forklarer kundeeierskapets prioritet. I partnerkanalen må samme konkurranses fag avklares.
3. **Filtrer på «Til avklaring».** I direktekanalen viser eksempelfilen to saker: én mangler ansvarsregel og én mangler område. Klikk på saken for forklaringen.
4. **Åpne «Bortsorterte konkurranser».** Her ser du det offentlige faggrunnlaget for de to sakene som ikke fikk nye oppgaver. Ingen treff i demoreglene er ikke en garanti for at saken er irrelevant i virkeligheten.

Søk kan finne tittel, kunde, mottaker, konkurransereferanse, fag og område. Sortering bruker tilbudsfrist eller tittel. Ukjent frist legges sist. «Nullstill» fjerner søk og filtre i den valgte kanalen.

Under oppdragsdetaljene kan du åpne «Kilder og dokumentlenker» og «Historikk i denne kanalen». Dokumentlenkene er fiktive, og ingen dokumenter er lastet ned. Historikken viser registrerte endringer; den later ikke som at oppgaven er sendt.

## Statusene betyr

| Status | Betydning |
| --- | --- |
| Mottaker foreslått | En mottaker finnes. Forslaget er verken godkjent eller levert. |
| Til avklaring | Programmet kunne ikke foreslå en mottaker. Begrunnelsen sier hvorfor. |
| Datakontroll | Opplysningene krever kontroll, for eksempel ved kildekonflikt eller endret tildelingsgrunnlag. |
| Avlyst | Konkurransen er merket avlyst. Oppgaven og historikken er beholdt. |

Et manglende hovedfag betyr ikke alltid avklaring: registrert kundeeier kan fortsatt foreslås i direkte salg. Statusen bygger derfor på utfallet av fordelingen, ikke bare på antall tomme felt.

## Hvis du bruker en annen database eller port

```sh
python -m mission_distribution serve --db runtime/demo.sqlite3 --port 8766
```

Åpne adressen som terminalen skriver ut. Hvis porten allerede brukes, stopp den andre demoen eller velg en annen port. Databasen velges ved oppstart, ikke gjennom et felt i nettsiden. En ny database starter tom; siden legger ikke inn eksempeldata automatisk.

## Avgrensning

Serveren lytter bare på din egen maskin, på 127.0.0.1. Visningen bruker ingen eksterne skrifter, bilder eller nettleserskript og trenger ingen nye Python-pakker.

Den har ingen pålogging. En lokal administratør kan åpne begge kanaler. Kanalvis filtrering og kontroll av oppgave-ID hindrer at en partnerforespørsel får direktekanalens interne oppgavedata, men dette er **ikke** ferdig tilgangsstyring for flere brukere. Den vises ikke som en produksjonsløsning.

Manuelt mottakerbytte finnes fortsatt i terminaldemoen. Godkjenning, tilbakemeldinger, redigering i nettleseren og AI kommer i egne steg. [Se utviklingsplanen](utviklingsplan.md).
