# Hvordan finner programmet fag og område?

Før programmet velger mottaker, vurderer det hva kunngjøringen gjelder. Denne delen bruker faste regler, ikke AI. En CPV-kode er en kode som beskriver hva som anskaffes. Den er ikke en fagkode på en ansatt.

## Tre mulige resultater

| Resultat | Hva skjer videre? |
| --- | --- |
| Relevant etter demoreglene | Programmet forsøker å finne mottaker i hver kanal. |
| Ukjent fag | Oppdraget går videre. Direkte salg kan fortsatt finne kundens registrerte selger. Uten et slikt treff må faget avklares. |
| Ingen relevante treff | Oppdraget og begrunnelsen lagres, men det opprettes ingen nye oppgaver. |

«Ingen treff» betyr at de tilgjengelige kodene og tekstene ikke traff **demotabellen**. Det er ikke et bevis på at oppdraget er irrelevant i virkeligheten. Derfor kan du se de bortsorterte sakene etterpå.

## Et eksempel

En oppdiktet kunngjøring gjelder service på et SD-anlegg. CPV-koden `50700000` og ordet «SD-anlegg» gir BA i eksempelreglene. Leveringsstedets fiktive kommunekode `9901` gir området Vest.

Direkte salg finner deretter kundens registrerte selger i den oppdiktede kundelisten. Partnerkanalen bruker BA og Vest i sin egen ansvarsliste. Fagvurderingen velger altså ikke ansatte selv.

## Slik brukes reglene

Reglene ligger i `demo_data/classification_rules.json`:

- **CPV:** Hvis flere regelprefikser treffer samme kode, brukes det lengste og mest spesifikke treffet.
- **Nøkkelord:** Tittel og beskrivelse søkes hver for seg. Treff kan legge til flere fag.
- **Hovedfag:** Et fagtreff på hoved-CPV bestemmer hovedfaget. Ellers brukes rekkefølgen BA, FS, SE. Denne rekkefølgen er et demovalg som kan endres i tabellen.
- **Brede koder:** Uten mer konkrete kode- eller nøkkelordtreff gir de ukjent fag. De gir ikke automatisk bortsortering.
- **Ekskluderte koder:** Koden gir ingen fagtreff. Andre koder eller nøkkelord i samme oppdrag kan fortsatt gi relevante treff.
- **Type:** Et prefiks i hoved-CPV gir installasjon, leveranse eller service. Uten et slikt treff står typen som ukjent.
- **Område:** Leveringskommunen brukes først. Mangler leveringssted, brukes innkjøpers kommune. Ved flere leveringsområder brukes innkjøpers kommune, og saken merkes `FLERE_OMRÅDER`.
- **Flagg:** Merkenavn merkes separat. Forhåndskunngjøring og markedsdialog merkes som tidlig fase når kildeposten oppgir denne typen.

BA, FS og SE behandles som kategorier; demoen antar ingen fullstendig fagliste. Kommunekodene 9901, 9902 og 9903 er oppdiktede. Tabellene er små demonstrasjonseksempler og ikke en komplett, godkjent fag- eller områdeinndeling.

Hvis et oppgitt leveringssted mangler i områdetabellen, lar demoen området stå ukjent fremfor å gjette. Dette er et konservativt demovalg som må avklares for en faktisk løsning.

## Se hele arbeidsflyten

Kjør fra prosjektmappen:

```sh
python3 -m mission_distribution ingest demo_data/source_batches/05-classification.json --db runtime/fagdemo.sqlite3
python3 -m mission_distribution tasks --channel direkte --db runtime/fagdemo.sqlite3
python3 -m mission_distribution tasks --channel indirekte --db runtime/fagdemo.sqlite3
python3 -m mission_distribution assessments --db runtime/fagdemo.sqlite3
```

Den siste kommandoen viser offentlig faggrunnlag for alle åtte konkurranser, inkludert de to bortsorterte. Den viser ingen interne mottakere eller kanalhistorikk.

Innlesingen bruker `preparation: "rules"`. Fag og område er ikke ferdig utfylt i disse kildepostene, men beregnes etter at tilgjengelige kildeopplysninger er samlet. Filformatet er vårt eget, ikke et bekreftet API-svar fra Doffin eller Mercell.

De eldre filene 01–04 og de ti `DEMO`-sakene bruker fortsatt ferdig utfylte fag og områder. De demonstrerer fordeling og oppdateringer uten denne nye fagvurderingen.

## Hva skjer når opplysningene endres?

- Samme innlesingsfil på nytt gir ingen ekstra oppgaver eller historikk.
- Motstridende sentrale kildefelt, også hoved-CPV, gir datakonflikt. Nye saker får avklaring fremfor en gjettet mottaker.
- Blir en tidligere bortsortert konkurranse relevant, kan en ny kildeversjon opprette de første oppgavene på samme lagrede konkurranse.
- Har konkurransen allerede en oppgave, bevares oppgave-ID og gjeldende mottaker. Endret fag eller område, eller bortfall av relevans, merkes for datakontroll. Markeringen bevares ved senere oppdateringer. Nettleserdemoen kan bekrefte kontroll av endret tildelingsgrunnlag ved lokal godkjenning. Den retter ikke kildedata eller regeltabeller og kan ikke overstyre bortfall av relevans, kildekonflikt eller mulig duplikat.
- Nye kildeopplysninger gjør tidligere lokal godkjenning utdatert. Gjeldende mottaker og oppgave-ID bevares.
- Vurderingen lagrer en identifikator for regelsettet som ble brukt. Endring i regelfilen vurderer ikke automatisk alle tidligere konkurranser på nytt. Det krever en ny funksjon; gjentatt innlesing av samme batch er fortsatt en handling uten endringer.

## Begrensninger vi må kjenne til

Dette er tekstsøk. Det forstår ikke forskjellen på «brannalarm» og «brannalarm inngår ikke». Bøyninger og alternative faguttrykk kan også mangle treff. Det er gode eksempler å bruke når vi senere vurderer om AI gir bedre resultater.

Klassifiseringen bruker den samlede postens valgte tittel og beskrivelse. Den leser ikke PDF-er, og den analyserer ikke alle historiske tekstversjoner. Nye kildeversjoner erstatter sin egen liste over tilleggskoder og leveringssteder; mellom kildenes gjeldende poster samles listene. Sletting og uttrykkelig tømming av felt er ikke fullt støttet.

CPV-formatet kontrolleres, men demoen verifiserer ikke at hver kode eller kontrollsiffer finnes i en offisiell kodetabell. Den beregner heller ikke flagget for kort frist i arbeidsdager. Verdi, avtaletype, entrepriseform og spørsmålsfrist er ikke med i denne versjonen.

Den lokale demoen har ingen pålogging. At en kommando bare viser offentlig faggrunnlag, erstatter ikke tilgangsstyring for en løsning med flere brukere.
