"""Loopback-only browser demo with explicit, version-checked local actions."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import parse_qs, urlsplit

from .approval import StaleProposalError
from .dashboard import DashboardActions, DashboardQuery, render_dashboard, render_error
from .models import Channel, DemoDataError, load_direct_rules, load_indirect_rules
from .storage import DemoStore


ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "web_assets"
CSP = "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"


def create_server(database: Path, port: int = 8765, rules_directory: Path = ROOT / "demo_data") -> ThreadingHTTPServer:
    database = database.resolve()
    # GET only reads; the two POST routes make explicit local changes.
    with DemoStore(database):
        pass
    csrf_token = secrets.token_urlsafe(32)

    def channel_rules(channel: Channel):
        if channel == Channel.DIRECT:
            return load_direct_rules(rules_directory / "direct_rules.json")
        return load_indirect_rules(rules_directory / "indirect_rules.json")

    class Handler(BaseHTTPRequestHandler):
        server_version = "LocalDemo"
        sys_version = ""

        def _reply(self, code: int, body: str | bytes, content_type: str = "text/html; charset=utf-8") -> None:
            encoded = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            # no-referrer nulls Origin on HTML form posts, including local ones.
            # same-origin preserves local Origin without sending referrers to other sites.
            # https://fetch.spec.whatwg.org/#origin-header
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(encoded)

        def _local_request(self) -> bool:
            # A local server must not accept a foreign site's host through DNS rebinding.
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "").casefold() not in allowed:
                self._reply(403, render_error("Åpne demoen via den lokale adressen som står i terminalen."))
                return False
            return True

        def do_GET(self) -> None:
            if not self._local_request():
                return
            path = urlsplit(self.path)
            assets = {"/assets/dashboard.css": ("dashboard.css", "text/css; charset=utf-8"),
                      "/assets/favicon.svg": ("favicon.svg", "image/svg+xml")}
            if path.path in assets:
                filename, content_type = assets[path.path]
                self._reply(200, (ASSETS / filename).read_bytes(), content_type)
                return
            if path.path != "/":
                self._reply(404, render_error("Siden finnes ikke. Bruk oppdragsoversikten."))
                return
            try:
                query = DashboardQuery.parse(parse_qs(path.query, keep_blank_values=True, max_num_fields=10))
                rules = channel_rules(query.channel)
                with DemoStore(database) as store:
                    # One SQLite snapshot keeps the list, detail and history consistent during ingestion.
                    store.connection.execute("BEGIN")
                    page = render_dashboard(store.tasks(query.channel), store.assessments(), query,
                                            DashboardActions(tuple(rules.people.values()), csrf_token))
                self._reply(200, page)
            except (DemoDataError, ValueError) as exc:
                self._reply(400, render_error(str(exc)))
            except (OSError, sqlite3.Error, KeyError, TypeError) as exc:
                self.log_error("Lokal visning feilet (%s)", type(exc).__name__)
                self._reply(500, render_error("Demodataene kunne ikke leses. Kontroller databasen og startguiden i README."))

        def do_POST(self) -> None:
            if not self._local_request():
                return
            if self.path not in {"/actions/reassign", "/actions/approve"}:
                self._reject_write()
                return
            origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if self.headers.get("Origin") is not None and self.headers["Origin"] not in origins:
                self._reply(403, render_error("Endringen må gjøres fra den lokale oppdragsoversikten."))
                return
            if self.headers.get_content_type() != "application/x-www-form-urlencoded" or self.headers.get("Transfer-Encoding"):
                self._reply(400, render_error("Ugyldig skjema. Ingen endring er utført."))
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise DemoDataError("Skjemaet mangler innhold eller er for stort. Ingen endring er utført.")
                values = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True,
                                  strict_parsing=True, max_num_fields=6)
                required = {"csrf_token", "channel", "task_id", "expected_revision"}
                allowed = required | ({"person_id"} if self.path == "/actions/reassign" else {"acknowledge_review"})
                if not required <= set(values) or set(values) - allowed or any(len(items) != 1 for items in values.values()):
                    raise DemoDataError("Ugyldig skjema. Oppdater siden før du prøver igjen.")
                form = {key: items[0] for key, items in values.items()}
                if not secrets.compare_digest(form["csrf_token"].encode("utf-8"), csrf_token.encode("utf-8")):
                    self._reply(403, render_error("Siden må oppdateres før du kan gjøre en endring. Ingen endring er utført."))
                    return
                channel = Channel(form["channel"])
                rules = channel_rules(channel)
                with DemoStore(database) as store:
                    if self.path == "/actions/reassign":
                        person = rules.people.get(form.get("person_id"))
                        if person is None:
                            raise DemoDataError("Velg en aktiv mottaker fra denne kanalen.")
                        store.reassign(form["task_id"], channel, person, expected_revision=form["expected_revision"])
                    else:
                        if form.get("acknowledge_review", "") not in {"", "yes"}:
                            raise DemoDataError("Ugyldig kontrollbekreftelse. Ingen endring er utført.")
                        store.approve(form["task_id"], channel, rules.people, form["expected_revision"],
                                      acknowledge_review=form.get("acknowledge_review") == "yes")
                # Redirect to the updated task without retaining a now-obsolete status filter.
                self.send_response(303)
                self.send_header("Location", DashboardQuery(channel=channel).url(task=form["task_id"]))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
            except StaleProposalError as exc:
                self._reply(409, render_error(str(exc)))
            except DemoDataError as exc:
                self._reply(400, render_error(str(exc)))
            except ValueError:
                self._reply(400, render_error("Ugyldig skjema. Ingen endring er utført."))
            except (OSError, sqlite3.Error) as exc:
                self.log_error("Lokal handling feilet (%s)", type(exc).__name__)
                self._reply(500, render_error("Handlingen kunne ikke lagres. Kontroller databasen og prøv igjen."))

        def _reject_write(self) -> None:
            self._reply(405, render_error("Denne visningen kan bare lese oppgaver. Ingen endring er utført."))

        do_PUT = _reject_write
        do_PATCH = _reject_write
        do_DELETE = _reject_write

        def log_message(self, format: str, *args) -> None:
            # Avoid printing search strings or task identifiers to browser-preview logs.
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(description="Åpne en lokal oppdragsoversikt. Oppdiktede data; ingen pålogging.")
    parser.add_argument("--db", type=Path, default=ROOT / "runtime" / "fagdemo.sqlite3", help="Samme demodatabase som brukes ved innlesing.")
    parser.add_argument("--port", type=int, default=8765, help="Lokal port, normalt 8765.")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Porten må være mellom 1 og 65535.")
    try:
        server = create_server(args.db, args.port)
    except (OSError, sqlite3.Error) as exc:
        parser.error(f"Kunne ikke starte den lokale demoen: {exc}")
    print(f"Oppdragsoversikt: http://127.0.0.1:{server.server_port}", flush=True)
    print("Lokal administratordemo med fiktive data. Mottaker og godkjenning lagres lokalt. Ingenting sendes.", flush=True)
    print("Stopp med Ctrl+C. Siden kan oppdateres etter ny innlesing fra en annen terminal.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDemoen er stoppet.")
    finally:
        server.server_close()
