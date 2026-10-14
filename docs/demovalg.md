# Valg i den første kjørbare demoen

Dette er demonstrasjonsvalg. Vi vet ikke hvordan arbeidsgiverens faktiske data eller systemer er organisert.

## Klargjorte oppdrag først

Oppdragene er oppdiktede og har allerede et hovedfag og et område, eller verdien `null` hvis opplysningen er ukjent. Ingen AI eller CPV-analyse har satt disse verdiene. Første del demonstrerer bare fordelingen etter at opplysningene er klargjort.

Fagkodene BA, FS og SE behandles som kategorier i demoen. Vi utvider ikke forkortelsene eller antar at vi kjenner den fullstendige faglisten.

De oppdiktede organisasjonsnumrene har ni sifre, men er ikke kontrollert mot et offentlig register. Områdene Vest, Øst og Nord er demonstrasjonsområder.

## Ansvar og fravær

- `active=true` betyr at en person kan motta oppdrag i denne demonstrasjonen.
- `active=false` betyr at personen er utilgjengelig. Det er ikke en direkte avlesning av fravær eller en faktisk konto.
- Hvert fag og område har høyst én ansvarlig regel per kanal. Dupliserte regler avvises.
- En inaktiv kundeeier uten registrert stedfortreder gir et forsøk på fordeling etter fag og område, med flagg om inaktiv eier.
- Når både kundeeieren og en registrert stedfortreder er inaktive, sendes saken til manuell avklaring.

## Navnelikhet

Navnelikhet brukes bare til å foreslå manuell avklaring i direkte salg, aldri til å bekrefte kundeeierskap. Vi bruker en enkel tekstsammenligning med en terskel på 0,9 som kan endres i demofilen. Dette tallet er ikke en AI-sannsynlighet eller en terskel bekreftet av arbeidsgiver.

## Hva kanalene får

Fordelingsfunksjonen for partnerkanalen får bare partnernes person- og ansvarsliste. Den laster ikke kundeeierskap. Offentlige flagg kan følge oppdraget; flagget om installert base kommer bare fra direktekanalens kundeliste.

Dette er et skille mellom dataene som funksjonene bruker. Den lokale terminaldemoen har ingen brukerpålogging og etablerer ikke et sikkert flerbrukersystem. Brukeren som har tilgang til prosjektmappen kan lese begge demofilene. Tilgangskontroll i et nettgrensesnitt må bygges og testes i et senere steg.

## Forslag er ikke levering

Alle resultater er forslag eller saker til manuell avklaring. Ingen oppgave blir opprettet i Planner, og ingen godkjenning registreres. Datoene er eksempeldata; fristendringer behandles ikke i denne første versjonen.

## De åtte eksempelsakene

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
