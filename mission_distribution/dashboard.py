"""Norwegian local dashboard, rendered without JavaScript or external assets."""

from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from urllib.parse import urlencode, urlsplit

from .approval import approval_blocker, approval_current, review_revision
from .models import Channel, DemoDataError, Person


STATUS_LABELS = {"alle": "Alle oppgaver", "forslag": "Mottaker foreslått", "uavklart": "Til avklaring",
                 "kontroll": "Datakontroll", "godkjent": "Godkjent lokalt",
                 "ny_godkjenning": "Må godkjennes på nytt", "avlyst": "Avlyst"}
FIELDS = {"buyer_org_number": "innkjøpers organisasjonsnummer", "main_trade": "hovedfag", "area": "område",
          "deadline": "tilbudsfrist", "main_cpv": "hoved-CPV", "buyer_municipality": "innkjøpers kommune",
          "notice_kind": "kunngjøringstype", "description": "beskrivelse", "title": "tittel",
          "document_urls": "dokumentlenker", "other_trades": "øvrige fag", "public_flags": "flagg",
          "buyer_name": "innkjøpers navn", "work_type": "oppdragstype"}
FLAGS = {"MERKENAVN": "Merkenavn nevnt", "TIDLIG_FASE": "Tidlig fase", "FLERE_OMRÅDER": "Flere områder",
         "MULIG_DUPLIKAT": "Mulig duplikat", "INSTALLERT_BASE": "Installert base",
         "EIER_INAKTIV": "Registrert eier er inaktiv"}


def text(value: object) -> str:
    return escape(str(value), quote=True)


def date_label(value: str | None) -> str:
    if not value:
        return "Ikke oppgitt"
    return date.fromisoformat(value).strftime("%d.%m.%Y")


def task_status(task: dict) -> str:
    if task["lifecycle"] == "avlyst":
        return "avlyst"
    if task.get("data_review_required"):
        return "kontroll"
    if approval_current(task, task["public_opportunity"]):
        return "godkjent"
    if task.get("approval"):
        return "ny_godkjenning"
    return "forslag" if task["owner"] else "uavklart"


@dataclass(frozen=True)
class DashboardActions:
    people: tuple[Person, ...]
    csrf_token: str


@dataclass(frozen=True)
class DashboardQuery:
    channel: Channel = Channel.DIRECT
    search: str = ""
    status: str = "alle"
    sort: str = "frist"
    selected: str | None = None

    @classmethod
    def parse(cls, values: dict[str, list[str]]) -> "DashboardQuery":
        if set(values) - {"channel", "q", "status", "sort", "task"} or any(len(items) != 1 for items in values.values()):
            raise DemoDataError("Ugyldig utvalg. Åpne oppdragsoversikten på nytt.")
        single = {key: items[0] for key, items in values.items()}
        try:
            channel = Channel(single.get("channel", "direkte"))
        except ValueError as exc:
            raise DemoDataError("Velg direkte salg eller partnerkanalen.") from exc
        status, sort = single.get("status", "alle"), single.get("sort", "frist")
        search = single.get("q", "").strip()
        if status not in STATUS_LABELS or sort not in {"frist", "tittel"} or len(search) > 200:
            raise DemoDataError("Ugyldig søk eller filter. Åpne oppdragsoversikten på nytt.")
        return cls(channel, search, status, sort, single.get("task") or None)

    def url(self, **changes) -> str:
        values = {"channel": self.channel.value, "q": self.search, "status": self.status, "sort": self.sort}
        values.update(changes)
        return "/?" + urlencode({key: value for key, value in values.items() if value})


def filter_tasks(tasks: list[dict], query: DashboardQuery) -> list[dict]:
    # Defend the view boundary even if a caller accidentally supplies a mixed list.
    own = [task for task in tasks if task["channel"] == query.channel.value]
    selected = []
    for task in own:
        public = task["public_opportunity"]["opportunity"]
        owner = task["owner"]["name"] if task["owner"] else ""
        searchable = " ".join(str(value or "") for value in (task["title"], task["competition_ref"],
                             public["buyer_name"], task["main_trade"], task["area"], owner)).casefold()
        if query.search.casefold() not in searchable:
            continue
        if query.status != "alle" and task_status(task) != query.status:
            continue
        selected.append(task)
    if query.sort == "frist":
        return sorted(selected, key=lambda task: (task["deadline"] or "9999-12-31", task["title"].casefold(), task["task_id"]))
    return sorted(selected, key=lambda task: (task["title"].casefold(), task["task_id"]))


def _pill(label: str, kind: str = "neutral") -> str:
    return f'<span class="pill {text(kind)}">{text(label)}</span>'


def _options(values: dict[str, str], selected: str) -> str:
    return "".join(f'<option value="{text(value)}"{" selected" if value == selected else ""}>{text(label)}</option>'
                   for value, label in values.items())


def _event(event: dict) -> str:
    kind, details = event["type"], event["details"]
    if kind == "forslag_opprettet":
        return "Mottakerforslag eller avklaringssak opprettet lokalt."
    if kind == "frist_endret":
        return f"Tilbudsfrist endret: {date_label(details['previous'])} → {date_label(details['current'])}."
    if kind == "manuelt_omfordelt":
        return f"Mottaker endret manuelt: {details['previous_owner_id'] or 'ingen mottaker'} → {details['new_owner_id']}."
    if kind == "mottaker_foreslått":
        return f"Tilleggsopplysninger ga et mottakerforslag: {details['owner_id']}."
    if kind == "avlyst":
        return "Konkurransen er merket avlyst."
    if kind == "opplysninger_endret":
        return "Oppdatert: " + ", ".join(FIELDS.get(field, field) for field in details["fields"]) + "."
    if kind == "datakontroll_endret":
        return "Grunnlaget for datakontroll er oppdatert. Se mangler og konflikter over."
    if kind == "fagvurdering_endret":
        labels = {"relevant": "relevant", "fag_ukjent": "ukjent fag", "ikke_relevant": "uten relevante treff"}
        return f"Fagvurdering oppdatert: {labels.get(details['current'], 'ukjent')}. Hovedfag: {details['main_trade'] or 'ukjent'}."
    if kind == "godkjent_lokalt":
        instant = datetime.fromisoformat(details["at"]).strftime("%d.%m.%Y %H:%M UTC")
        return f"Forslaget til {details['owner_id']} er godkjent lokalt av demobruker uten pålogging ({instant}). Ingen levering."
    if kind == "godkjenning_utdatert":
        return "Tidligere godkjenning gjelder ikke lenger: " + details["reason"]
    if kind == "datakontroll_bekreftet":
        return "Lokal demobruker har bekreftet kontroll av det endrede tildelingsgrunnlaget."
    return "Oppgaven har en registrert historikkhendelse."


def _controls(task: dict, actions: DashboardActions) -> str:
    public = task["public_opportunity"]
    if task["lifecycle"] != "aktiv":
        return '<section class="detail-section"><h3>Avlyst konkurranse</h3><p>Mottakerbytte og godkjenning er ikke tilgjengelig.</p></section>'
    fields = {"csrf_token": actions.csrf_token, "channel": task["channel"], "task_id": task["task_id"],
              "expected_revision": review_revision(task, public)}
    hidden = "".join(f'<input type="hidden" name="{key}" value="{text(value)}">' for key, value in fields.items())
    people = {person.id: person for person in actions.people if person.active and person.channel.value == task["channel"]}
    owner_id = task["owner"]["id"] if task["owner"] else ""
    options = '<option value="">Velg en aktiv mottaker</option>'
    options += _options({person.id: person.name + " · " + (", ".join(person.trade_codes) or "fag ikke oppgitt")
                         for person in sorted(people.values(), key=lambda person: person.name.casefold())}, owner_id)
    blocked = approval_blocker(task, public)
    if blocked is None and owner_id not in people:
        blocked = "Mottakeren er ikke aktiv i ansvarsliste for denne kanalen. Velg en aktiv mottaker først."
    if blocked:
        approval_html = f'<p class="approval-blocked">{text(blocked)}</p><button type="button" disabled>Godkjenn lokalt</button>'
    elif approval_current(task, public):
        instant = datetime.fromisoformat(task["approval"]["approved_at"]).strftime("%d.%m.%Y %H:%M UTC")
        approval_html = f'<div class="approval-confirmed"><strong>Godkjent lokalt</strong><p>{text(instant)} · lokal demobruker uten pålogging.</p><p>Ingen oppgave eller varsel er sendt.</p></div>'
    else:
        review = ('<label class="checkbox"><input type="checkbox" name="acknowledge_review" value="yes" required>'
                  '<span>Jeg har kontrollert de endrede opplysningene og mener valgt mottaker er riktig.</span></label>') if task.get("data_review_required") else ""
        outdated = '<p class="approval-blocked">Tidligere godkjenning gjelder ikke lenger. Se gjennom det oppdaterte forslaget.</p>' if task.get("approval") else ""
        approval_html = f'{outdated}<form method="post" action="/actions/approve">{hidden}{review}<button type="submit">Godkjenn lokalt</button></form>'
    return f'''<section class="detail-section actions"><h3>Kontroller forslaget</h3>
      <form method="post" action="/actions/reassign">{hidden}<label for="person_id">Mottaker i denne kanalen</label>
      <div class="action-row"><select id="person_id" name="person_id" required>{options}</select><button type="submit">Lagre mottaker</button></div></form>
      <p class="muted">Bare aktive mottakere fra denne kanalen vises. Endringen gjelder denne oppgaven, ikke ansvarstabellen. Et mottakerbytte må godkjennes separat.</p>
      <div class="approval-action">{approval_html}</div></section>'''


def _detail(task: dict, actions: DashboardActions | None = None) -> str:
    stored, public = task["public_opportunity"], task["public_opportunity"]["opportunity"]
    assessment = stored.get("classification")
    owner = task["owner"]
    owner_name = owner["name"] if owner else "Må avklares manuelt"
    explanation = text(task["explanation"])
    capacity = f'<p class="muted">Kapasitet: {text(owner["capacity"])}. Kapasitet brukes ikke i fordelingen.</p>' if owner else ""
    flags = " ".join(_pill(FLAGS.get(flag, flag)) for flag in task["flags"])
    warnings = []
    if task.get("data_review_required"):
        warnings.append("Opplysningene krever kontroll. " + ("Gjeldende mottaker er beholdt." if owner else "Mottaker må avklares."))
    if stored["missing_fields"]:
        warnings.append("Ikke oppgitt: " + ", ".join(FIELDS.get(field, field) for field in stored["missing_fields"]) + ".")
    if stored["conflicts"]:
        warnings.append("Kildene er uenige om: " + ", ".join(FIELDS.get(field, field) for field in stored["conflicts"]) + ".")
    if stored["possible_duplicate_ids"]:
        warnings.append("Mulig duplikat. Konkurransen er beholdt separat for kontroll.")
    warning_html = ('<div class="attention"><strong>Dette må vi være oppmerksomme på</strong><ul>' +
                    "".join(f"<li>{text(warning)}</li>" for warning in warnings) + "</ul></div>") if warnings else ""
    if assessment:
        hits = []
        for hit in assessment["hits"]:
            if hit["kind"] == "cpv":
                label = "Hoved-CPV" if hit["role"] == "main" else "Tilleggs-CPV"
                hits.append(f"{label} {hit['code']} → {hit['trade']} (regel {hit['matched_prefix']})")
            else:
                fields = ", ".join(FIELDS.get(field, field) for field in hit["fields"])
                hits.append(f"«{hit['phrase']}» → {hit['trade']} i {fields}")
        hits += [f"Bred kode {code}: gir ikke et bestemt fag" for code in assessment["broad_codes"]]
        hits += [f"Kode {code}: gir ingen fagtreff" for code in assessment["excluded_codes"]]
        evidence = f'<p>{text(assessment["explanation"])}</p>'
        evidence += '<ul class="evidence">' + "".join(f"<li>{text(hit)}</li>" for hit in hits) + "</ul>"
        evidence += f'<p class="muted">{text(assessment["area_explanation"])}</p>'
    else:
        evidence = '<p>Fag og område er ferdig utfylt i denne eldre demoposten.</p>'
    source_items = []
    for source in stored["source_refs"]:
        instant = datetime.fromisoformat(source["modified_at"]).strftime("%d.%m.%Y %H:%M UTC")
        source_items.append(f'<li><strong>{text(source["source"].capitalize())}</strong><br>'
                            f'<span class="muted">{text(source["record_id"])} · kildeversjon {text(instant)}</span></li>')
    documents = []
    for url in public["document_urls"]:
        parsed = urlsplit(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            documents.append(f'<li><a href="{text(url)}" target="_blank" rel="noopener noreferrer">'
                             f'Fiktiv dokumentlenke · {text(parsed.hostname)}</a></li>')
    document_html = ('<ul class="evidence">' + "".join(documents) + "</ul>"
                     '<p class="muted">Dette er eksempellenker. Ingen dokumentfiler er lastet ned.</p>') if documents else '<p class="muted">Ingen dokumentlenker er oppgitt.</p>'
    events = "".join(f"<li>{text(_event(event))}</li>" for event in reversed(task["events"]))
    controls = _controls(task, actions) if actions else ""
    foot = ("Godkjenning lagres bare lokalt. Ingen oppgave eller varsel er sendt." if actions
            else "Dette er en lesevisning. Ingen oppgave eller varsel er sendt.")
    return f'''<aside class="detail" aria-labelledby="detail-heading">
      <div class="detail-top"><p class="eyebrow">VALGT OPPDRAG</p>{_pill(STATUS_LABELS[task_status(task)], task_status(task))}
      <h2 id="detail-heading">{text(task['title'])}</h2><p class="reference">{text(task['competition_ref'] or 'Uten konkurransereferanse')}</p></div>
      <section class="detail-section"><h3>{'Hvorfor denne mottakeren?' if owner else 'Hvorfor må oppdraget avklares?'}</h3><p class="owner">{text(owner_name)}</p>
      <p>{explanation}</p>{capacity}<p class="rule-code">Årsak: {text(task['reason_code'])}</p>{flags}</section>
      {warning_html}
      {controls}
      <section class="detail-section"><h3>Fag og område</h3><dl class="facts">
      <div><dt>Hovedfag</dt><dd>{text(task['main_trade'] or 'Ukjent')}</dd></div>
      <div><dt>Øvrige fag</dt><dd>{text(', '.join(public['other_trades']) or 'Ingen')}</dd></div>
      <div><dt>Område</dt><dd>{text(task['area'] or 'Ukjent')}</dd></div>
      <div><dt>Type</dt><dd>{text(public.get('work_type') or 'Ikke vurdert')}</dd></div></dl>{evidence}</section>
      <section class="detail-section"><h3>Offentlig kunngjøringsgrunnlag</h3><dl class="facts">
      <div><dt>Innkjøper</dt><dd>{text(public['buyer_name'])}</dd></div>
      <div><dt>Organisasjonsnummer</dt><dd>{text(public['buyer_org_number'] or 'Ikke oppgitt')}</dd></div>
      <div><dt>Tilbudsfrist</dt><dd>{text(date_label(task['deadline']))}</dd></div></dl>
      <p>{text(public['description'] or 'Beskrivelse er ikke oppgitt.')}</p></section>
      <details class="detail-section"><summary>Kilder og dokumentlenker</summary><ul class="sources">{''.join(source_items)}</ul>{document_html}</details>
      <details class="detail-section"><summary>Historikk i denne kanalen <span class="muted">({len(task['events'])})</span></summary>
      <ol class="history">{events or '<li>Ingen hendelser registrert.</li>'}</ol>
      <p class="reference">Oppgave-ID: {text(task['task_id'])}</p></details>
      <div class="detail-foot">{foot}</div>
    </aside>'''


def render_dashboard(tasks: list[dict], assessments: list[dict], query: DashboardQuery,
                     actions: DashboardActions | None = None) -> str:
    own = [task for task in tasks if task["channel"] == query.channel.value]
    visible = filter_tasks(own, query)
    chosen = next((task for task in visible if task["task_id"] == query.selected), None) if query.selected else (visible[0] if visible else None)
    if query.selected and chosen is None:
        raise DemoDataError("Oppgaven finnes ikke i denne kanalens utvalg. Åpne oversikten på nytt.")
    direct = query.channel == Channel.DIRECT
    channel_name = "Direkte salg" if direct else "Partnerkanalen"
    subtitle = ("Kundens registrerte selger prioriteres. Ellers brukes fag og område." if direct
                else "Mottaker foreslås fra partnerkanalens egen ansvarsliste for fag og område.")
    tab_items = []
    for channel, label in ((Channel.DIRECT, "Direkte salg"), (Channel.INDIRECT, "Partnerkanalen")):
        current = channel == query.channel
        aria = ' aria-current="page"' if current else ""
        tab_items.append(f'<a class="channel-tab{" current" if current else ""}" '
                         f'href="{text(DashboardQuery(channel=channel).url())}"{aria}>{label}</a>')
    tabs = "".join(tab_items)
    metrics = [("Oppgaver i kanalen", len(own)), ("Venter godkjenning", sum(task_status(task) in {"forslag", "ny_godkjenning"} for task in own)),
               ("Godkjent lokalt", sum(task_status(task) == "godkjent" for task in own)),
               ("Til avklaring", sum(task_status(task) == "uavklart" for task in own)),
               ("Datakontroll", sum(task_status(task) == "kontroll" for task in own))]
    metrics_html = "".join(f'<div class="metric"><span>{text(label)}</span><strong>{count}</strong></div>' for label, count in metrics)
    rows = []
    for task in visible:
        selected = chosen is not None and task["task_id"] == chosen["task_id"]
        public = task["public_opportunity"]["opportunity"]
        link = text(query.url(task=task["task_id"]))
        rows.append(f'''<tr{' class="selected"' if selected else ''}>
          <td><a class="task-link" href="{link}"{' aria-current="true"' if selected else ''}>{text(task['title'])}</a>
          <span class="buyer">{text(public['buyer_name'])}</span></td>
          <td>{text(task['main_trade'] or 'Ukjent')}<span class="buyer">{text(task['area'] or 'Ukjent område')}</span></td>
          <td>{text(task['owner']['name'] if task['owner'] else 'Må avklares')}</td>
          <td class="date">{text(date_label(task['deadline']))}</td>
          <td>{_pill(STATUS_LABELS[task_status(task)], task_status(task))}</td></tr>''')
    if own and not visible:
        empty = '<div class="empty"><h3>Ingen oppgaver passer søket</h3><p>Prøv et annet søk eller fjern filteret.</p></div>'
    elif not own:
        empty = '<div class="empty"><h3>Ingen oppgaver er lest inn ennå</h3><p>Les inn eksempeldataene fra startguiden i README, og oppdater siden.</p></div>'
    else:
        empty = ""
    table = (f'<div class="table-scroll"><table><caption class="sr-only">Oppgaver i {channel_name}</caption>'
             '<thead><tr><th scope="col">Oppdrag</th><th scope="col">Fag / område</th><th scope="col">Mottaker</th>'
             '<th scope="col">Tilbudsfrist</th><th scope="col">Status</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>') if rows else empty
    discarded = [item for item in assessments if not item["classification"]["should_route"] and not item["conflicting_fields"]]
    discarded_html = "".join(f'<li><strong>{text(item["title"])}</strong><p>{text(item["classification"]["explanation"])}</p>'
                             f'<span class="reference">{text(item["competition_ref"] or "Uten referanse")}</span></li>' for item in discarded)
    excluded = (f'<details class="discarded"><summary>Bortsorterte konkurranser <span class="count">{len(discarded)}</span></summary>'
                '<p class="muted">Ingen treff i demoreglene er ikke et bevis på at oppdraget er irrelevant i virkeligheten. '
                'Her vises bare offentlig faggrunnlag.</p><ul>' + discarded_html + '</ul></details>') if discarded else ""
    detail = _detail(chosen, actions) if chosen else '<aside class="detail empty"><h2>Oppdragsdetaljer</h2><p>Velg et oppdrag når det finnes i utvalget.</p></aside>'
    return f'''<!doctype html><html lang="nb"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{channel_name} · Oppdragsfordeling</title><link rel="stylesheet" href="/assets/dashboard.css"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"></head>
    <body><a class="skip" href="#main">Hopp til oppdragene</a>
    <header class="topbar"><div class="brand"><span class="brand-mark" aria-hidden="true">↗</span><span>Oppdragsfordeling<small>Lokal prototype</small></span></div>
    <span class="demo-label"><span aria-hidden="true">●</span> Oppdiktede data</span></header>
    <main id="main"><section class="intro"><div><p class="eyebrow">FRA KUNNGJØRING TIL ANSVARLIG</p><h1>Oppdragsoversikt</h1>
    <p class="lead">Se hva programmet fant, hvem det foreslår og hva som må avklares.</p></div>
    <div class="demo-note"><strong>Dette er en administratordemo.</strong><p>Ingen AI eller eksterne tjenester er koblet til. Ingen oppgaver er sendt.
    Lokal bruker kan åpne begge kanaler. Pålogging og tilgangsstyring gjenstår.</p></div></section>
    <nav class="channel-nav" aria-label="Velg salgskanal">{tabs}</nav>
    <section class="channel-intro"><div><h2>{channel_name}</h2><p>{subtitle}</p></div>
    <a class="refresh" href="{text(query.url(task=query.selected))}">Oppdater visningen ↻</a></section>
    <section class="metrics" aria-label="Oversikt for valgt kanal">{metrics_html}</section>
    <div class="workspace"><section class="overview" aria-labelledby="overview-heading"><div class="panel-heading"><h2 id="overview-heading">Oppdrag</h2>
    <span class="muted">Viser {len(visible)} av {len(own)}</span></div>
    <form class="filters" method="get" action="/"><input type="hidden" name="channel" value="{query.channel.value}">
    <div class="search"><label for="q">Søk i oppdrag</label><input id="q" type="search" name="q" maxlength="200" value="{text(query.search)}" placeholder="Oppdrag, kunde eller mottaker"></div>
    <div><label for="status">Status</label><select id="status" name="status">{_options(STATUS_LABELS, query.status)}</select></div>
    <div><label for="sort">Sorter etter</label><select id="sort" name="sort">{_options({'frist': 'Tilbudsfrist', 'tittel': 'Tittel'}, query.sort)}</select></div>
    <button type="submit">Vis</button><a class="reset" href="{text(DashboardQuery(channel=query.channel).url())}">Nullstill</a></form>
    {table}<p class="table-note">Klikk på et oppdrag for å se begrunnelse og historikk.</p>{excluded}</section>{detail}</div>
    <footer>Alle mottakere, kunder og oppdrag er fiktive. Fag- og områdetabellene er demonstrasjonsvalg.
    <span>Godkjenninger gjelder bare den lokale demoen. Tilbakemeldinger og ekstern levering gjenstår.</span></footer></main></body></html>'''


def render_error(message: str) -> str:
    return f'''<!doctype html><html lang="nb"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Oppdragsfordeling · Meldingen kunne ikke vises</title><link rel="stylesheet" href="/assets/dashboard.css"></head>
    <body><main><section class="detail error"><p class="eyebrow">LOKAL DEMO</p><h1>Visningen kunne ikke åpnes</h1><p>{text(message)}</p>
    <a class="refresh" href="/">Til oppdragsoversikten</a></section></main></body></html>'''
