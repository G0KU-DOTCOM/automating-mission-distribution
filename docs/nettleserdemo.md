# Oppdragsoversikten i nettleseren

Denne versjonen lar deg forstå mottakerforslag, velge mottaker og godkjenne lokalt. Den sender ingen oppgaver eller varsler.

## Start

Åpne terminalen i prosjektmappen. Med prosjektets venv aktivert:

```sh
python -m mission_distribution serve
```

Åpne http://127.0.0.1:8765 i nettleseren. Terminalen må stå åpen. Stopp med Ctrl+C.

Har du en eldre versjon kjørende, stopp den og start igjen. En oppdatering av nettsiden alene laster ikke den nye Python-koden.

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
| Godkjent lokalt | Valgt mottaker og opplysningene er godkjent i demoen. Ingenting er sendt. |
| Må godkjennes på nytt | Mottaker eller kildegrunnlag er endret etter forrige godkjenning. |
| Avlyst | Konkurransen er merket avlyst. Oppgaven og historikken er beholdt. |

Et manglende hovedfag betyr ikke alltid avklaring: registrert kundeeier kan fortsatt foreslås i direkte salg. Statusen bygger derfor på utfallet av fordelingen, ikke bare på antall tomme felt.

## Velg mottaker og godkjenn

1. Åpne «Demo: leveranse av adgangskontroll» i direkte salg. Saken mangler en registrert ansvarlig for SE × Nord.
2. Under «Kontroller forslaget», velg en aktiv mottaker fra denne kanalen. I demodataene har Demo Erik fagkodene BA, FS og SE. Trykk «Lagre mottaker».
3. Du får et manuelt mottakerforslag. Det er **ikke** godkjent ennå. Trykk «Godkjenn lokalt» etter å ha sett gjennom opplysningene.
4. Statusen blir «Godkjent lokalt». Åpne historikken for å se mottakerbyttet og godkjenningen. Partnerkanalens mottaker og godkjenning påvirkes ikke.

Et mottakerbytte gjelder bare den eksisterende oppgaven. Det fyller ikke automatisk hullet i ansvarstabellen og velger ikke nye personer ved hjelp av AI. Kapasitet vurderes heller ikke automatisk.

Registreringen viser «lokal demobruker uten pålogging», med tidspunkt i UTC. Demoen kjenner ikke identiteten til personen ved tastaturet. Godkjenningen er ikke en autentisert godkjenning hos arbeidsgiver, en kontraktssignering eller levering til Microsoft 365.

Velger du den samme mottakeren som allerede står der, skjer ingen endring. Gjentatt godkjenning av samme uendrede forslag gir ikke flere godkjenningshendelser. Mottakerbytte etter godkjenning gjør den tidligere godkjenningen utdatert.

## Når må du kontrollere på nytt?

- En ny frist, beskrivelse, dokumentlenke eller kildeversjon gjør tidligere godkjenning utdatert. Demoen er bevisst konservativ: også en ny kildeversjon med samme feltverdier krever ny gjennomgang.
- Oppgave-ID og gjeldende mottaker bevares. Oppdateringen er fortsatt samme oppdrag.
- Endret fag eller område kan kreve at du bekrefter en kontrollboks før ny godkjenning. Bekreftelsen fjerner kontrollmarkeringen for dette tildelingsgrunnlaget.
- Kildekonflikt, mulig duplikat eller bortfall av relevans kan ikke overstyres med kontrollboksen. Disse forholdene må avklares først. Et eget grensesnitt for slik retting gjenstår.
- Avlyste oppgaver kan verken få ny mottaker eller godkjennes.
- Manglende fag eller område blokkerer ikke i seg selv lokal godkjenning når kundeeier eller et manuelt valg gir en mottaker. Manglene vises fortsatt, og demoen fyller dem ikke inn.

Hvis du sender et skjema fra en gammel nettleserside etter at oppgaven er endret, avvises handlingen. Åpne oversikten på nytt og se gjennom de nye opplysningene. Ved oppdatering av programmet må du også hente en ny side før handlinger kan utføres.

## Hvis du bruker en annen database eller port

```sh
python -m mission_distribution serve --db runtime/demo.sqlite3 --port 8766
```

Åpne adressen som terminalen skriver ut. Hvis porten allerede brukes, stopp den andre demoen eller velg en annen port. Databasen velges ved oppstart, ikke gjennom et felt i nettsiden. En ny database starter tom; siden legger ikke inn eksempeldata automatisk.

## Avgrensning

Serveren lytter bare på din egen maskin, på 127.0.0.1. Visningen bruker ingen eksterne skrifter, bilder eller nettleserskript og trenger ingen nye Python-pakker.

Den har ingen pålogging. En lokal administratør kan åpne begge kanaler. Kanalvis filtrering og kontroll av oppgave-ID hindrer at en partnerforespørsel får direktekanalens interne oppgavedata, men dette er **ikke** ferdig tilgangsstyring for flere brukere. Den vises ikke som en produksjonsløsning.

Manuelt mottakerbytte finnes både i nettleseren og terminaldemoen. Lokal godkjenning er en egen handling i nettleseren. Rettelser av kildedata og regeltabeller, tilbakemeldinger, pålogging, AI og faktisk levering gjenstår. [Se utviklingsplanen](utviklingsplan.md).
