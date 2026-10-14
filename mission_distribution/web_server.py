"""Loopback-only, read-only browser preview for the local administrator demo."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlsplit

from .dashboard import DashboardQuery, render_dashboard, render_error
from .models import DemoDataError
from .storage import DemoStore


ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "web_assets"
CSP = "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"


def create_server(database: Path, port: int = 8765) -> ThreadingHTTPServer:
    database = database.resolve()
    # Initialize an empty demo if needed; HTTP requests never ingest or edit business data.
    with DemoStore(database):
        pass

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
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            # A local server must not accept a foreign site's host through DNS rebinding.
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "").casefold() not in allowed:
                self._reply(403, render_error("Åpne demoen via den lokale adressen som står i terminalen."))
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
                with DemoStore(database) as store:
                    # One SQLite snapshot keeps the list, detail and history consistent during ingestion.
                    store.connection.execute("BEGIN")
                    page = render_dashboard(store.tasks(query.channel), store.assessments(), query)
                self._reply(200, page)
            except (DemoDataError, ValueError) as exc:
                self._reply(400, render_error(str(exc)))
            except (OSError, sqlite3.Error, KeyError, TypeError) as exc:
                self.log_error("Lokal visning feilet (%s)", type(exc).__name__)
                self._reply(500, render_error("Demodataene kunne ikke leses. Kontroller databasen og startguiden i README."))

        def _reject_write(self) -> None:
            self._reply(405, render_error("Denne visningen kan bare lese oppgaver. Ingen endring er utført."))

        do_POST = _reject_write
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
    print("Lokal administratordemo med fiktive data. Ingen oppgaver blir godkjent, endret eller sendt.", flush=True)
    print("Stopp med Ctrl+C. Siden kan oppdateres etter ny innlesing fra en annen terminal.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDemoen er stoppet.")
    finally:
        server.server_close()
