# Valg i den første kjørbare demoen

Dette er demonstrasjonsvalg. Vi vet ikke hvordan arbeidsgiverens faktiske data eller systemer er organisert.

## Klargjorte og regelvurderte oppdrag

De ti første eksempelsakene og kildebatchene 01–04 er oppdiktede og har allerede et hovedfag og et område, eller verdien `null` hvis opplysningen er ukjent. Første del demonstrerer bare fordelingen etter at opplysningene er klargjort.

De åtte `FAG`-sakene og kildebatch 05 bruker i stedet regler for CPV, nøkkelord og oppdiktede kommunekoder. Det er ingen AI. De små tabellene, fagprioriteten og håndteringen av ukjente leveringssteder er demonstrasjonsvalg. [Fagvurderingen](fagvurdering.md) forklarer resultatene og begrensningene.

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

Nettleserdemoen viser én kanal om gangen og avviser en oppgave-ID som ikke finnes i den valgte kanalens utvalg. Den har fortsatt ingen pålogging; den lokale administratoren kan bytte kanal. Dette er en lesevisning på egen maskin, ikke faktisk tilgangsstyring mellom innloggede brukere.

## Forslag er ikke levering

Alle resultater er forslag eller saker til manuell avklaring. Ingen oppgave blir opprettet i Planner, og ingen godkjenning registreres. Innlesingsdemoen lagrer lokale oppgaver og følger fristendringer i eksempeldataene. Den sender ikke varsler.

## Innlesing og oppdateringer

Innlesingsdemoen bruker vårt eget format for fiktive kildeposter. Feltene for kilde-ID, felles konkurransereferanse og endringstid er demonstrasjonsdata. Vi har ikke bekreftet tilsvarende felter eller garantier i de virkelige API-ene.

En lokal database bevarer konkurranser, kildeversjoner, oppgaver og kanalvis historikk. En kjent kilde-ID eller felles referanse beholder konkurransens identitet ved fristendring. Uten disse bruker demoen kombinasjonen organisasjonsnummer, normalisert tittel og frist hvis den gir ett entydig treff. Det er en demoregel og ingen garanti for at slike poster faktisk gjelder samme konkurranse.

Hvis bare innkjøper og tittel matcher, eller kombinasjonsnøkkelen gir flere treff, opprettes en separat konkurranse med flagget `MULIG_DUPLIKAT`. Automatisk sammenslåing av slike saker er ikke implementert.

Det nyeste oppgitte endringstidspunktet brukes til å velge kjente feltverdier. Dette er et eksplisitt demovalg, ikke en antakelse om at en bestemt kilde alltid er korrekt. Motstridende sentrale opplysninger vises som konflikt. Nye konfliktsaker får årsaken `DATA_KONFLIKT` og krever avklaring. Eksisterende oppgaver beholder mottakeren og merkes for datakontroll.

Manglende verdier sletter ikke tidligere kjent informasjon. Dokumentlenker samles, men filene lastes ikke ned. Sletting av dokumenter og uttrykkelig fjerning av feltverdier er ikke implementert.

Oppdateringer beholder gjeldende mottaker og det opprinnelige tildelingsgrunnlaget. Ved endret regelberegnet hovedfag eller område, eller bortfall av relevans, merkes en allerede tildelt oppgave for kontroll. Den slettes eller omfordeles ikke automatisk. En uavklart oppgave uten mottaker kan få et nytt forslag når tilleggsopplysninger gir en regel. Den beholder samme oppgave-ID. Manuell omfordeling er ikke godkjenning eller levering.

Avlysning merker eksisterende lokale oppgaver. En konkurranse som først leses inn som avlyst, lagres uten nye salgsoppgaver. Automatisk gjenåpning av avlyste oppgaver og kontraktstildelinger er ikke implementert.

Databasen er kun for en lokal administratordemo. Kanalfiltrering av oppgaver og historikk er kontrollert med tester, men erstatter ikke brukerpålogging eller tilgangsstyring i et produksjonssystem.

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
