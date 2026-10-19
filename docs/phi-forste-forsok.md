# Første faktiske Phi-forsøk

Dette er et lite forsøk med våre egne fiktive saker, ikke en representativ måling av norske anskaffelser. Ingen mottakere, oppgaver eller godkjenninger ble endret.

## Oppsett og resultat

- Dato: 19. oktober 2026.
- Lokal modell: `phi4-mini:3.8b`, komprimert som Q4_K_M.
- Modellavtrykk: `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753`.
- Ollama: 0.40.6.
- Spørsmålsversjon: `phi-fag-demo-1`.
- Datagrunnlag: de åtte medfølgende sakene PHI-001–PHI-008.
- Alle åtte forespørslene fikk modellsvar. Ingen av svarene oppfylte sitatkravene: **0 av 8 gyldige svar, 8 avvist**.

Dette betyr ikke at alle enkeltvurderinger av fag var feil. Hele svaret for en sak avvises ved første valideringsfeil, og de avviste svarene brukes ikke til å beregne faglig samsvar med demofasiten.

## Hva feilet konkret?

I PHI-001 er beskrivelsen «Oppdiktet vedlikehold av brannalarmanlegg.». Phi svarte blant annet:

```json
{
  "BA": {
    "status": "inngår",
    "sitat": "I denne demoen: arbeid på SD-anlegg og sentral styring/overvåking av byggets tekniske anlegg."
  }
}
```

Dette er et faktisk utdrag fra modellsvar, ikke et simulert eksempel. Teksten er hentet fra vår definisjon av BA, ikke fra oppdraget. BA-statusen er også forskjellig fra vår forhåndsdefinerte demofasit. I PHI-005, som bare beskriver generelle tekniske arbeider, bruker modellen også fagdefinisjonene som sitater og svarer at alle tre fag inngår.

Sitatkontrollen avdekker derfor en reell sammenblanding av referansebeskrivelser og oppdragstekst. Andre svar har også omskrivinger og små tekstendringer; for eksempel «SD-anlegg ingår ikke.» i PHI-008, mens kildeteksten bruker «inngår».

## Hva kan vi konkludere?

- Den lokale forbindelsen og modellkjøringen fungerer.
- Kombinasjonen av denne modellen, komprimeringen, instruksjonene og svarformatet gir ikke pålitelige resultater i dette forsøket.
- Instruksjonene legger kategoridefinisjoner og oppdragstekst i samme brukermelding. Dette er en svakhet ved oppsettet vi laget, ikke bare et problem vi kan tilskrive modellens generelle evner.
- Det er ikke grunnlag for å la Phi endre fag eller mottaker i arbeidsflyten.

Vi prøvde også avgrensede instruksendringer med tydeligere skille mellom referanse og oppdrag, samt ett spørsmål per fag, på fire av sakene. Noen varianter ga flere gyldige sitater, men fortsatt feil fag eller «uklart» på tydelige saker. Dette var utviklingsforsøk med flere endringer, ikke en kontrollert sammenligning på et separat testsett. De dokumenterer ikke en ferdig forbedring.

Spørsmålsversjon 1 og demofasiten er beholdt uendret i programmet slik at resultatet kan undersøkes og sammenlignes. Vi har lagt til innsyn i avviste svar. En senere variant må få egen versjon og prøves på flere, nye saker.

## Undersøk svaret selv

Fra prosjektmappen, på Mac:

```sh
.venv/bin/python -m mission_distribution ai-review --case PHI-001 --diagnostics
```

Bruk `--all --json --diagnostics` for en maskinlesbar rapport over alle sakene. Avvist modelltekst vises separat fra gyldige vurderinger og får ingen samsvarsscore. Programmet returnerer en feilkode når minst ett svar avvises, selv om alle modellsvarene ble mottatt.

På utviklingsmaskinen er rårapporten lagret i `runtime/phi-evaluation/phi-v1-2026-10-19.json`. Den holdes utenfor Git og følger ikke nedlastingen fra GitHub. Modellen kan svare annerledes på andre maskiner eller etter oppdateringer. Dette er ingen garanti for identiske svar ved gjentakelse.
