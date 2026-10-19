# Oppdragsoversikten i nettleseren

Denne versjonen lar deg forstå mottakerforslag, velge mottaker og godkjenne lokalt. Den sender ingen oppgaver eller varsler.

## Første oppstart

Følg [startguiden i README](../README.md#slik-prøver-du-demoen-første-gang). På Windows dobbeltklikker du `Start-demo.cmd` etter at Python er installert og prosjektet er pakket ut. På Mac/Linux kjører du `python3 start_demo.py`. Startprogrammet ordner eget miljø, eksempeldata og server, og åpner nettleseren når siden svarer.

Nettadressen `127.0.0.1` betyr din egen PC. En lenke til denne adressen starter ikke programmet, og gir ikke tilgang til noen andres demo. Eirik må gjennomføre oppsettet på sin egen maskin for å bruke denne lokale versjonen.

Prosjektets Python-miljø (`.venv`) og databasen (`runtime/fagdemo.sqlite3`) følger ikke med fra GitHub. De opprettes lokalt i startguiden. Det er derfor ikke nok å laste ned prosjektet og trykke på nettleserlenken.

Det er ingen `requirements.txt` å installere fra nå: alle Python-modulene programmet bruker, følger med Python. Ikke kjør `pip install -r requirements.txt`; filen finnes ikke, og ingen ekstra pakker er nødvendige. Miljøet brukes likevel for å holde dette prosjektet adskilt fra andre Python-prosjekter.

Ved første innlesing blir ni fiktive kildeposter til åtte konkurranser. Seks konkurranser får én lokal oppgave per kanal, altså tolv oppgaver totalt. To konkurranser sorteres bort og vises separat. På en ny database har direktekanalen fire mottakerforslag og to avklaringssaker; partnerkanalen har tre av hver.

## Start igjen senere

På Windows: dobbeltklikk `Start-demo.cmd` i prosjektmappen igjen. På Mac/Linux: kjør `python3 start_demo.py` igjen.

La vinduet stå åpent mens du bruker nettleseren. Stopp med **Ctrl+C**. Oppgavene blir liggende til neste gang. Startprogrammet leser den samme eksempelfilen på nytt, men en allerede behandlet fil gir ingen ekstra oppgaver og endrer ikke tidligere manuelle valg eller godkjenninger.

Har du en eldre versjon kjørende, stopp den og start igjen. En oppdatering av nettsiden alene laster ikke den nye Python-koden. Bruk adressen fra den nye oppstarten, ikke et gammelt bokmerke med en bestemt oppgave-ID; slike ID-er kan være forskjellige på ulike PC-er.

## Hvis det ikke virker

| Det du ser | Hva du gjør |
| --- | --- |
| Nettleseren får ikke kontakt | Start serveren fra prosjektmappen. Vent på adressen i terminalen og la terminalen stå åpen. Lenken alene starter ikke serveren. |
| `No module named mission_distribution` | Du står sannsynligvis i feil mappe. Bruk mappen som inneholder både `README.md` og undermappen `mission_distribution`. |
| `python3`, `py` eller `python` finnes ikke | Installer Python fra [python.org](https://www.python.org/downloads/), åpne terminalen på nytt og kontroller versjonen. På Windows kan `python` brukes i stedet for `py -3` hvis det starter riktig Python-versjon. |
| Python er eldre enn 3.11 | Installer en støttet versjon og opprett prosjektets miljø med den versjonen før du fortsetter. |
| `.venv` eller Python-filen under den mangler | Bruk startfilen til å lage miljøet på denne maskinen. Et eksisterende miljø fra en annen PC skal ikke kopieres. Hvis startfilen sier at miljøet er feil, gi den lokale `.venv`-mappen et annet navn og start igjen. |
| Oversikten er tom | Bruk startfilen, som leser inn eksempeldata i riktig database. Ved manuell oppstart må innlesing og server bruke samme database. |
| «Address already in use» eller porten er opptatt | En annen server kan allerede kjøre. Stopp den i dens terminal, eller velg en annen port som vist lenger nede. |
| Oppstartsvinduet viser en feil | Les meldingen før du lukker vinduet. Startfilen laster ikke ned Python automatisk og overskriver ikke et uforenlig miljø. |
| Ny knapp mangler, eller et skjema avvises etter oppdatering | Stopp gammel server, start den nye versjonen og hent siden på nytt. |

For å fylle en tom oversikt, åpne en annen terminal i prosjektmappen og kjør én av disse:

Mac / Linux:

```sh
.venv/bin/python -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
```

Oppdater nettsiden etterpå. Gjentatt innlesing av den samme filen lager ikke ekstra oppgaver. Nettsiden leser lagrede data; den henter ikke noe fra Doffin eller Mercell.

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

## Hvis porten allerede er i bruk

Stopp den gamle demoen i dens vindu, eller velg en annen port. Startfilen stopper ikke en annen server automatisk.

Fra PowerShell i prosjektmappen:

```powershell
.\Start-demo.cmd --port 8766
```

På Mac/Linux:

```sh
python3 start_demo.py --port 8766
```

Bruk adressen som står i vinduet. Hvis du vil starte uten automatisk nettleser, legg til `--no-browser`. `--prepare-only` klargjør miljø og eksempeldata uten å starte serveren; dette brukes også i de automatiske testene.

## Hvis du bruker en annen database

Startfilen bruker alltid prosjektets `runtime/fagdemo.sqlite3`. For en annen database bruker du den manuelle serverkommandoen, for eksempel på Windows:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m mission_distribution serve --db runtime/annen-demo.sqlite3 --port 8766
```

Innlesing må bruke samme database. En ny database starter tom. Startfilen sletter eller nullstiller ikke tidligere data.

## Avgrensning

Serveren lytter bare på din egen maskin, på 127.0.0.1. Visningen bruker ingen eksterne skrifter, bilder eller nettleserskript og trenger ingen nye Python-pakker.

Den har ingen pålogging. En lokal administratør kan åpne begge kanaler. Kanalvis filtrering og kontroll av oppgave-ID hindrer at en partnerforespørsel får direktekanalens interne oppgavedata, men dette er **ikke** ferdig tilgangsstyring for flere brukere. Den vises ikke som en produksjonsløsning.

Manuelt mottakerbytte finnes både i nettleseren og terminaldemoen. Lokal godkjenning er en egen handling i nettleseren. Rettelser av kildedata og regeltabeller, tilbakemeldinger, pålogging, AI i nettleservisningen og faktisk levering gjenstår. Et eget [lokalt Phi-forsøk](lokal-ai.md) finnes i terminalen, uten å endre oppgavene. [Se utviklingsplanen](utviklingsplan.md).

## Kontroll av oppstarten

Oppstarten kontrolleres automatisk gjennom [GitHub Actions](https://github.com/G0KU-DOTCOM/automating-mission-distribution/actions/workflows/tests.yml) på Windows, Mac og Linux med Python 3.11 og 3.13. Åpne siste kjøring og se resultatet; et oppsett for tester er ikke i seg selv bevis på at siste kjøring har bestått.

Testene prøver et nytt miljø og en ny database, en mappe med mellomrom og norske tegn, oppstart fra en annen arbeidsmappe, serverens nettside og at manuell mottaker og godkjenning bevares ved neste oppstart. Windows-jobbene prøver også selve `Start-demo.cmd`. De automatiske testene åpner ikke en fysisk nettleser på mottakerens PC.

Startfilen bruker Windows sin `Scripts/python.exe` og UTF-8 for norske tegn. Det trengs ikke aktivering av PowerShell-skript. Dette bygger på [Pythons dokumentasjon for miljøer og Python-filstier](https://docs.python.org/3/library/venv.html#how-venvs-work).
