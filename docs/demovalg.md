# Valg i den første kjørbare demoen

Dette er demonstrasjonsvalg. Vi vet ikke hvordan arbeidsgiverens faktiske data eller systemer er organisert.

## Klargjorte oppdrag først

Oppdragene er oppdiktede og har allerede et hovedfag og et område, eller verdien `null` hvis opplysningen er ukjent. Ingen AI eller CPV-analyse har satt disse verdiene. Første del demonstrerer bare fordelingen etter at opplysningene er klargjort.

Fagkodene BA, FS og SE behandles som kategorier i demoen. Vi utvider ikke forkortelsene eller antar at vi kjenner den fullstendige faglisten.

De oppdiktede organisasjonsnumrene har ni sifre, men er ikke kontrollert mot et offentlig register. Områdene Vest, Øst og Nord er demonstrasjonsområder.

## Ansvar og fravær

- `active=true` betyr at personen er registrert som aktiv for tildeling i demoens ansvarsliste. Det betyr ikke at vedkommende har ledig kapasitet.
- `active=false` gjør personen utilgjengelig for tildeling etter disse reglene. Verdien er ikke hentet fra en faktisk konto eller fraværskilde.
- `capacity` er en separat demoverdi: `ukjent`, `ledig` eller `opptatt`. Den vises med resultatet, men påvirker ikke fordelingsreglene. Ukjent kapasitet betyr ikke ledig kapasitet.
- Hvert fag og område har høyst én ansvarlig regel per kanal. Dupliserte regler avvises.
- En inaktiv kundeeier uten registrert stedfortreder gir et forsøk på fordeling etter fag og område, med flagg om inaktiv eier.
- Når både kundeeieren og en registrert stedfortreder er inaktive, sendes saken til manuell avklaring.

## Fagtilhørighet og avtalt ansvar

Personens `trade_codes` beskriver fagtilhørighet i de oppdiktede dataene. Ansvarstabellen beskriver hvem som er valgt som ansvarlig for et fag og område. Dette er forskjellige opplysninger. En fagkode alene gir ikke rett til å motta oppdraget.

Kundeeierskap kan også gjelde en kunde på tvers av fag. Vi lar derfor ikke personens fagkoder overstyre registrert kundeeierskap. Om eierskapet i en faktisk løsning skal gjelde hele kunden eller kunden per fag, er fortsatt åpent.

## Tidligere kundekontakt

Kundens `prior_contact_ids` viser oppdiktede personer som har hatt kontakt tidligere. Opplysningen lagres bare i direktekanalens kundeliste og påvirker ikke tildelingen. Kundens `owner_id` beskriver registrert eierskap og prioriteres etter de avklarte reglene.

Vi vet ikke hvilke kontaktopplysninger som finnes i et faktisk CRM, eller om og hvordan de skal gi prioritet. Demoen har ingen modell som beregner «beste match» på tvers av alle ansatte.

## Navnelikhet

Navnelikhet brukes bare til å foreslå manuell avklaring i direkte salg, aldri til å bekrefte kundeeierskap. Vi bruker en enkel tekstsammenligning med en terskel på 0,9 som kan endres i demofilen. Dette tallet er ikke en AI-sannsynlighet eller en terskel bekreftet av arbeidsgiver.

## Hva kanalene får

Fordelingsfunksjonen for partnerkanalen får bare partnernes person- og ansvarsliste. Den laster ikke kundeeierskap. Offentlige flagg kan følge oppdraget; flagget om installert base kommer bare fra direktekanalens kundeliste.

Dette er et skille mellom dataene som funksjonene bruker. Den lokale terminaldemoen har ingen brukerpålogging og etablerer ikke et sikkert flerbrukersystem. Brukeren som har tilgang til prosjektmappen kan lese begge demofilene. Tilgangskontroll i et nettgrensesnitt må bygges og testes i et senere steg.

## Forslag er ikke levering

Alle resultater er forslag eller saker til manuell avklaring. Ingen oppgave blir opprettet i Planner, og ingen godkjenning registreres. Datoene er eksempeldata; fristendringer behandles ikke i denne første versjonen.

## De ti eksempelsakene

| Sak | Hva den demonstrerer |
| --- | --- |
| DEMO-001 | Aktiv kundeeier prioriteres foran en annen fagansvarlig. |
| DEMO-002 | Kundeeier kan velges selv om faget er ukjent. Partnerkanalen må avklare faget. |
| DEMO-003 | Ansvarlig er inaktiv, men stedfortrederen er aktiv. |
| DEMO-004 | Kjent navn uten riktig organisasjonsnummer, og manglende partnerregel. |
| DEMO-005 | Området er ukjent. |
| DEMO-006 | Ansvarlig og stedfortreder er begge inaktive. |
| DEMO-007 | Inaktiv kundeeier uten stedfortreder gir forsøk på fag og område. |
| DEMO-008 | Kundeeier og registrert stedfortreder er begge inaktive. |
| DEMO-009 | Det finnes personer med passende fagkode, men ingen ansvarsregel for fag og område. Saken må avklares. |
| DEMO-010 | En aktiv kundeeier er markert som opptatt og tilhører et annet fag. En annen person har tidligere kontakt. Registrert kundeeierskap styrer fortsatt forslaget; kapasitet vurderes ikke. |
