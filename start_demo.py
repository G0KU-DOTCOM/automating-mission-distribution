"""Prepare the local demo and start it from any working directory, including Windows."""

import sys

if sys.version_info < (3, 11):
    print("Demoen krever Python 3.11 eller nyere. Installer Python fra https://www.python.org/downloads/")
    raise SystemExit(1)

import argparse
from http.client import HTTPConnection
import os
from pathlib import Path
import subprocess
from threading import Thread
import time
import venv
import webbrowser


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "runtime" / "fagdemo.sqlite3"


class StartupError(Exception):
    pass


def python_environment():
    environment = os.environ.copy()
    # Preserve Norwegian text in Windows consoles and redirected child-process output.
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def environment_python(root, windows=None):
    if windows is None:
        windows = os.name == "nt"
    return root / ".venv" / ("Scripts/python.exe" if windows else "bin/python")


def prepare_environment(root):
    interpreter = environment_python(root)
    environment = root / ".venv"
    if not environment.exists():
        print("Lager prosjektets eget Python-miljø. Dette trengs bare første gang.", flush=True)
        venv.create(environment, with_pip=True)
    if not interpreter.is_file():
        raise StartupError("Mappen .venv inneholder ikke riktig Python for denne PC-en. "
                           "Miljøer fra en annen PC kan ikke kopieres. Gi .venv et annet navn og start igjen.")
    result = subprocess.run([str(interpreter), "-X", "utf8", "-c",
                             "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"],
                            cwd=root, env=python_environment(), capture_output=True)
    if result.returncode:
        raise StartupError("Prosjektets .venv bruker ikke en fungerende Python 3.11 eller nyere. "
                           "Gi .venv et annet navn og start igjen med en støttet Python-versjon.")
    return interpreter


def open_when_ready(port, process):
    url = f"http://127.0.0.1:{port}/"
    deadline = time.monotonic() + 10
    while process.poll() is None and time.monotonic() < deadline:
        connection = HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            connection.request("GET", "/")
            response = connection.getresponse()
            response.read()
            if response.status == 200:
                if not webbrowser.open(url):
                    print(f"Åpne nettleseren selv på {url}", flush=True)
                return
        except OSError:
            pass
        except webbrowser.Error:
            print(f"Åpne nettleseren selv på {url}", flush=True)
            return
        finally:
            connection.close()
        time.sleep(.1)
    if process.poll() is None:
        print(f"Nettleseren ble ikke åpnet automatisk. Prøv {url}", flush=True)


def run_server(interpreter, root, port, open_browser):
    command = [str(interpreter), "-X", "utf8", "-m", "mission_distribution", "serve",
               "--db", str(root / "runtime" / "fagdemo.sqlite3"), "--port", str(port)]
    process = subprocess.Popen(command, cwd=root, env=python_environment(), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    browser_started = False
    try:
        for line in process.stdout:
            print(line, end="", flush=True)
            # This line is printed only after our server successfully binds the port.
            if open_browser and not browser_started and line.startswith(f"Oppdragsoversikt: http://127.0.0.1:{port}"):
                browser_started = True
                Thread(target=open_when_ready, args=(port, process), daemon=True).start()
        return process.wait()
    except KeyboardInterrupt:
        # Ctrl+C normally reaches the child through the shared console as well.
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        process.stdout.close()


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Klargjør og åpne den lokale demoen. Ingen oppgaver sendes.")
    parser.add_argument("--port", type=int, default=8765, help="Lokal port, normalt 8765.")
    parser.add_argument("--no-browser", action="store_true", help="Start uten å åpne nettleseren automatisk.")
    parser.add_argument("--prepare-only", action="store_true", help="Klargjør miljø og eksempeldata uten å starte serveren.")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Porten må være mellom 1 og 65535.")
    try:
        interpreter = prepare_environment(ROOT)
        print("Klargjør oppdiktede oppdrag. Eksisterende mottakerbytter og godkjenninger beholdes.", flush=True)
        subprocess.run([str(interpreter), "-X", "utf8", "-m", "mission_distribution", "ingest",
                        str(ROOT / "demo_data" / "source_batches" / "05-classification.json"),
                        "--db", str(DATABASE)], cwd=ROOT, env=python_environment(), check=True)
        if args.prepare_only:
            print("Miljø og eksempeldata er klare.", flush=True)
            return 0
        result = run_server(interpreter, ROOT, args.port, not args.no_browser)
        if result:
            print("Serveren kunne ikke starte. Hvis porten er opptatt, stopp den eldre demoen "
                  "eller bruk --port 8766.", flush=True)
        return result
    except KeyboardInterrupt:
        print("\nOppstarten er avbrutt.", flush=True)
        return 0
    except (StartupError, OSError, subprocess.SubprocessError) as exc:
        print(f"Kunne ikke starte demoen: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
