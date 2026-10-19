# Prøv Phi lokalt, uten betalte API-er

Dette er et eget forsøk ved siden av nettleserdemoen. Phi vurderer bare medfølgende, oppdiktede tekster. Den velger ingen ansatte og endrer ingen oppgaver eller godkjenninger. Du trenger ikke en API-nøkkel eller nye Python-pakker.

**Status:** Koden og feilhåndteringen testes med tydelig simulerte modellsvar. I tillegg er modellen kjørt lokalt på alle åtte saker: alle svarte, men ingen svar oppfylte sitatkravene. Dette er ikke grunnlag for automatisk bruk. [Se det faktiske forsøket](phi-forste-forsok.md).

## 1. Installer Ollama

Last ned gratisappen fra [ollama.com/download](https://ollama.com/download), installer og åpne den. Bruk lokal kjøring. Du trenger ikke kjøpe abonnement, legge til betalingskort eller opprette en skykonto for dette forsøket.

På Mac krever dagens Ollama macOS 14 eller nyere. [Se systemkrav](https://docs.ollama.com/macos). Det finnes også en [Windows-utgave](https://docs.ollama.com/windows).

Vi prøver **Phi-4-mini-instruct**, ikke den større Phi-4. Kommandoen under laster ned en komprimert utgave på omtrent 2,5 GB. Minnebehovet under kjøring er større enn filstørrelsen og avhenger også av tekstlengden. 16 GB RAM er et rimelig utgangspunkt for disse korte tekstene; faktisk hastighet må prøves.

## 2. Hold modellen lokal

Forsøket bruker bare `phi4-mini:3.8b` på adressen `127.0.0.1:11434`. Det følger ikke omdirigeringer og har ingen innstilling for eksternt API eller skymodell.

Ollamas skyfunksjoner kan i tillegg slås av. Avslutt Ollama helt før dette, og åpne appen igjen etterpå.

På Mac, kjør i terminalen:

```sh
launchctl setenv OLLAMA_NO_CLOUD 1
```

På Windows: åpne «Rediger miljøvariabler for kontoen», opprett brukervariabelen `OLLAMA_NO_CLOUD` med verdien `1`, og start Ollama på nytt.

Dette er Ollamas [dokumenterte innstilling for lokal kjøring](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features). Innstillingen gjelder også annen lokal bruk av Ollama frem til du endrer den igjen. Nedlasting og oppdatering av app/modell krever fortsatt internett.

## 3. Last ned modellen én gang

Åpne en ny terminal eller PowerShell etter installasjonen og kjør:

```sh
ollama pull phi4-mini:3.8b
```

Vent til nedlastingen er ferdig. [Modellfilen og lisensen](https://ollama.com/library/phi4-mini:3.8b) kan brukes lokalt uten betalte API-kall. Din egen maskin bruker strøm og lagringsplass.

Hvis `ollama` ikke finnes, åpne appen og en ny terminal. På Mac kan appen be om å gjøre terminalkommandoen tilgjengelig.

## 4. Kontroller at alt er klart

Åpne terminalen i prosjektmappen, som inneholder `README.md` og `mission_distribution`. Bruk én av kommandoene:

Mac / Linux:

```sh
.venv/bin/python -m mission_distribution ai-review --check
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m mission_distribution ai-review --check
```

Hvis prosjektets `.venv` ikke finnes ennå, følg først [den vanlige startguiden](../README.md#slik-prøver-du-demoen-første-gang). Sjekken sier at Ollama og modellen er klare når modellen er lastet ned og appen svarer. Den kjører ingen fagvurdering.

## 5. Prøv én sak

Mac / Linux:

```sh
.venv/bin/python -m mission_distribution ai-review
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m mission_distribution ai-review
```

Første kjøring kan ta tid mens modellen lastes inn i minnet. Hvert modellkall har en grense på to minutter. Standardeksemplet gjelder «service på brannalarmanlegg». Dagens nøkkelordregel overser dette sammensatte ordet; forsøket viser hva Phi svarer, uten å anta at Phi svarer riktig.

Du ser dagens regelresultat og modellens vurdering av hvert fag: «inngår», «inngår_ikke» eller «uklart». Modellen må oppgi et ordrett tekstgrunnlag for svar som ikke er «uklart». Programmet avviser et oppdiktet sitat. At sitatet finnes, beviser likevel ikke at tolkningen er riktig.

Legg til `--case PHI-002` for negasjonseksemplet eller `--all` for alle åtte saker. `--json` viser et maskinlesbart resultat som du selv kan lagre. Fremdriftsmeldinger vises separat. Ingen rapportfil eller database skrives automatisk.

Ved avviste svar kan du legge til `--diagnostics`. Da vises den faktiske modellteksten som ble avvist, separat fra gyldige vurderinger. Den får ingen samsvarsscore. Uten dette valget vises bare feilen, slik at normalutskriften er kort.

```sh
.venv/bin/python -m mission_distribution ai-review --case PHI-001 --diagnostics
```

Oppsummeringen skiller mellom antall forsøk, svar som oppfyller format- og sitatkrav, og avviste svar. Det er ikke det samme som antall faglig riktige svar.

For eksempel, på Mac:

```sh
.venv/bin/python -m mission_distribution ai-review --all
```

## Hva sammenligner vi?

### Se hva programmet gir modellen

Du kan vise den nøyaktige forespørselen fra Python uten å kontakte Ollama:

```sh
.venv/bin/python -m mission_distribution ai-review --case PHI-001 --show-request
```

På Windows bruker du `.\.venv\Scripts\python.exe -X utf8` i stedet for `.venv/bin/python`. Legg til `--json` hvis du bare vil ha maskinlesbar utskrift.

Visningen inneholder instruksjonene, tittel og beskrivelse, fagdefinisjonene, svarskjemaet og innstillingene. Forventede svar og ansattdata er ikke med. Den er samme forespørsel som vanlig kjøring bygger, men den sendes ikke. Ollama trenger derfor ikke kjøre.

Bruk `--diagnostics` i en vanlig kjøring for å se avvist modelltekst. Dette er modellens svar, ikke en observasjon av dens interne beregninger. En ny forklaring modellen skriver på bestilling, er heller ikke bevis på hvordan den kom frem til det opprinnelige svaret.

Ved kontroll av den installerte modellen 19. oktober 2026 oppga Ollama `completion` og `tools`, men ingen `thinking`-metadata. Det dokumenterer ingen egen innsynsvisning for denne modellen. [Ollama beskriver hvordan støtte for «thinking» kan kontrolleres](https://docs.ollama.com/capabilities/thinking). Modeller som tilbyr slik tekst, viser fortsatt ikke alle interne beregninger.

Hva som påvirker svarene, kan undersøkes med nye fiktive tekstpar der én opplysning endres om gangen, for eksempel «inngår» mot «inngår ikke». Slike forsøk viser hvordan svaret reagerer på endringen. De beviser ikke hvilken intern mekanisme som ga svaret.

### Eksempler og sammenligningsgrunnlag

De åtte eksemplene omfatter sammensatte ord, uttrykkelig utelatte fag, bakgrunnsomtale, flere fag, generell tekst uten nok opplysninger, alternative faguttrykk og en beskrivelse som peker annerledes enn CPV-koden.

Fagdefinisjonene og forventede svar ligger i `demo_data/phi_review_examples.json`. De er våre demonstrasjonsvalg, ikke bekreftede arbeidsgiverdata. Forventede svar ble skrevet før modellkjøringen og sendes ikke til modellen.

Phi får bare tittel, beskrivelse og demodefinisjonene av fag. Den får ikke CPV, ansattnavn, kundeeierskap, ansvarslister, kapasitet eller fasiten. CPV blir fortsatt brukt av dagens regelvurdering. Ulikt resultat kan derfor skyldes både tolkning og forskjellig datagrunnlag. CPV-eksemplet demonstrerer dette; modellen får ikke overstyre koden.

«Samsvar med vår demofasit» teller bare hvor mange av de tre fagstatusene som er like våre forhåndsdefinerte svar. Det er ingen kalibrert sannsynlighet eller representativ måling av kvalitet i produksjon. Vi sammenligner heller ikke automatisk hovedfag med alle fag som inngår; hovedfagsprioriteten ligger fortsatt i reglene.

Resultatet inneholder modellfilens identifikator fra Ollama, versjonen av spørsmålene og et avtrykk av forespørselen. Det gjør det lettere å se hvilke forutsetninger som endres mellom forsøk. Fast temperatur og startverdi er ikke en garanti for identiske svar på all maskinvare eller etter programoppdateringer.

## Hvis det stopper

| Melding | Hva du gjør |
| --- | --- |
| «Fikk ikke svar fra lokal Ollama» | Åpne Ollama. Hvis en modellvurdering tok mer enn to minutter, prøv én sak igjen og lukk andre tunge programmer. |
| «Den lokale modellen mangler» | Kjør `ollama pull phi4-mini:3.8b` og prøv sjekken igjen. |
| «Sitatet finnes ikke» eller «ufullstendig svar» | Svaret er avvist. Det blir ikke gjort om til en tildeling. Ta vare på feilmeldingen når vi vurderer om modellen er egnet. |

Vanlig nettleserdemo og startfil trenger fortsatt ikke Ollama. AI-vurderingen vises foreløpig **bare i terminalen**. Tilkobling til nettleservisningen og vurdering av kvalitet gjenstår.

## Dokumentasjon

- [Microsofts modellkort: språk, lisens og begrensninger](https://huggingface.co/microsoft/Phi-4-mini-instruct)
- [Ollamas lokale API](https://docs.ollama.com/api/chat)
- [Strukturerte JSON-svar](https://docs.ollama.com/capabilities/structured-outputs)

Disse kildene er kontrollert 19. oktober 2026. Tilgjengelighet og programkrav kan endres.
