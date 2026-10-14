# Utviklingsplan for prototypen

Dette er arbeidsgrunnlaget for utviklingen. Fordeling og vedvarende innlesing virker med oppdiktede data. Kravene under gjelder hele prototypen og er ikke alle implementert ennå.

## Ferdig i første del

- Oppdiktede person- og ansvarslister, separat for hver kanal.
- Innlesing som stopper ugyldige eller motstridende ansvarslister.
- Fordelingsforslag med kundeeierskap, fag og område, stedfortredere og årsak til manuell avklaring.
- En terminaldemo og tester av eksempelsakene.
- Egne personfagkoder, opplysninger om tidligere kundekontakt og kapasitetsstatus, tydelig adskilt fra reglene som bestemmer ansvar.

## Ferdig i andre del

- Validerte, fiktive kildeposter i vårt eget format.
- Felles konkurransepost med kildereferanser, feltopprinnelse, manglende informasjon og synlige konflikter.
- Duplikatkontroll med stabile kilde-ID-er, felles referanser og en dokumentert kombinasjonsnøkkel.
- Usikre duplikater beholdes separat og merkes for kontroll.
- Lokale oppgaver med stabile ID-er, endret frist, dokumentlenker, avlysning og kanalvis historikk.
- Manuell omfordeling som bevares ved neste oppdatering.
- Gjentatte batcher og eldre kildeversjoner lager ikke nye oppgaver eller tilbakeruller nyere data.
- Hele innlesingen lagres samlet. Ved feil tilbakerulles batchen, og siste vellykkede lesegrense endres ikke.

Brukerpålogging, tilgangskontroll i endepunkter, faktisk API-innhenting, fagklassifisering, godkjenning og ekstern levering gjenstår. Innlesingsdemoen laster ikke ned dokumentfiler.

## Avgrensning

- Første versjon kjører lokalt og bruker bare tydelig merkede, oppdiktede oppdrag, personer, kunder og ansvarslister.
- Eksempeldata viser vårt interne format. De skal ikke omtales som bekreftede svar fra Doffin- eller Mercell-API-ene.
- Ingen tilkobling til Microsoft 365, CRM eller kilde-API-er er etablert eller testet.
- AI-modell skal velges sammen med brukeren. Simulerte svar må merkes og må ikke presenteres som faktisk modellbruk.
- Repoet skal være offentlig. Originaldokumenter fra arbeidsgiver, private meldinger, virkelige kunde- og ansattopplysninger og nøkler skal holdes utenfor repoet.

## Hva vi skal kontrollere

1. Registrert kundeeier prioriteres foran fag og område i direkte salg. Partnerkanalen bruker sine egne ansvarslister.
2. Hvert relevant oppdrag får én ansvarlig per kanal, eller en sak til kanalens eget avklaringsmottak med begrunnelse.
3. Partnerkanalen kan ikke hente direktekanalens kundeeierskap, installerte base, tildelinger eller interne aktivitetshistorikk gjennom programmets endepunkter. Separate faner alene er ikke tilstrekkelig.
4. Gjentatt innlesing gir ikke ekstra oppgaver for samme bekreftede konkurranse. Usikre duplikatmatcher skal være synlige og ikke slå sammen konkurranser automatisk.
5. Endret frist oppdaterer samme oppgave. Oppdateringer følger gjeldende eier når mottakeren er endret manuelt.
6. Fravær, inaktive ansvarlige og stedfortredere, usikre kundematcher og manglende fordelingsregler gir forklarte utfall.
7. Skyggemodus krever godkjenning i riktig kanal før levering. Godkjenning og automatisk levering skal være separate handlinger.
8. Tilbakemeldinger skiller feil fag, feil mottaker og faglig relevante oppdrag som velges bort av kommersielle grunner.

## Rekkefølge

1. Beskriv avgrensningen, åpne beslutninger og forventede resultater.
2. Lag datamodellen, ansvarslister og oppdiktede eksempelsaker.
3. Bygg innlesing, fordelingsregler, oppdateringer og kontroll av kanaltilgang. Kontroller dette med tester av konkrete situasjoner.
4. Lag et grensesnitt for beslutninger, godkjenning, manuell omfordeling, oppdateringer og tilbakemeldinger.
5. Avklar AI-modellens rolle og leverandør, sammenlign med de faste reglene og beskriv Microsoft-integrasjonene som gjenstår.

## Beslutninger som gjenstår

- Gjelder kundeeierskap hele kunden eller ett fag hos kunden?
- Hvem skal eie oppdrag som omfatter flere fag?
- Hvilke oppdrag skal partnerkanalen få?
- Hvordan defineres områder og fravær, og hvem vedlikeholder ansvarsdataene?
- Hvordan måles ledig kapasitet, og skal en opptatt kundeeier gi vikar, alternativ mottaker eller manuell avklaring?
- Skal tidligere kundekontakt gi prioritet, og hvilke bekreftede kontaktopplysninger kan brukes?
- Hvilken AI-modell skal brukes, hvilke data kan den behandle, og når kan et forslag brukes?

Valg vi gjør for demonstrasjonen skal være tydelige og ikke fremstilles som bekreftede beslutninger hos arbeidsgiver.

## Commits

Commit-titler skal beskrive konkrete endringer. Teksten skal forklare de berørte filene og hvorfor endringen ble gjort. Kode og tester for samme funksjon kan ligge i én commit. Selvstendige endringer skal skilles.
