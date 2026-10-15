"""Check first startup and persistence from a separate project folder on every OS."""

from http.client import HTTPConnection
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import start_demo


ROOT = Path(__file__).resolve().parents[1]


class StartupTests(unittest.TestCase):
    def test_windows_and_posix_interpreter_paths(self):
        root = Path("project")
        self.assertEqual(start_demo.environment_python(root, windows=True), root / ".venv" / "Scripts" / "python.exe")
        self.assertEqual(start_demo.environment_python(root, windows=False), root / ".venv" / "bin" / "python")

    def test_foreign_or_incomplete_environment_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = root / ".venv"
            environment.mkdir()
            marker = environment / "keep.txt"
            marker.write_text("existing environment", encoding="utf-8")
            with self.assertRaises(start_demo.StartupError):
                start_demo.prepare_environment(root)
            self.assertEqual(marker.read_text(encoding="utf-8"), "existing environment")

    def test_child_encoding_is_utf8_without_changing_parent_environment(self):
        with patch.dict(os.environ, {"PYTHONUTF8": "0", "PYTHONIOENCODING": "ascii"}):
            environment = start_demo.python_environment()
            self.assertEqual(environment["PYTHONUTF8"], "1")
            self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")
            self.assertEqual(os.environ["PYTHONUTF8"], "0")

    def test_browser_is_not_opened_after_server_has_already_failed(self):
        with patch.object(start_demo.webbrowser, "open") as opened:
            process = unittest.mock.Mock()
            process.poll.return_value = 1
            start_demo.open_when_ready(8765, process)
            opened.assert_not_called()

    def test_browser_opens_only_after_server_returns_a_page(self):
        with patch.object(start_demo, "HTTPConnection") as connection, patch.object(start_demo.webbrowser, "open", return_value=True) as opened:
            process = unittest.mock.Mock()
            process.poll.return_value = None
            connection.return_value.getresponse.return_value.status = 200
            start_demo.open_when_ready(8766, process)
            opened.assert_called_once_with("http://127.0.0.1:8766/")
            connection.return_value.close.assert_called_once()


class StartupIntegrationTests(unittest.TestCase):
    def test_fresh_prepare_server_and_restart_keep_manual_owner_and_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Demo med mellomrom ÆØÅ"
            root.mkdir()
            for folder in ("mission_distribution", "demo_data"):
                shutil.copytree(ROOT / folder, root / folder, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(ROOT / "start_demo.py", root / "start_demo.py")
            environment = start_demo.python_environment()
            # Running outside the project must still use paths relative to the start file.
            prepare = [sys.executable, "-X", "utf8", str(root / "start_demo.py"), "--prepare-only"]
            result = subprocess.run(prepare, cwd=directory, env=environment, capture_output=True,
                                    encoding="utf-8", check=True, timeout=90)
            self.assertIn("Miljø og eksempeldata er klare", result.stdout)
            interpreter = start_demo.environment_python(root)
            database = root / "runtime" / "fagdemo.sqlite3"
            command = [str(interpreter), "-X", "utf8", "-m", "mission_distribution"]

            def run(*arguments):
                return subprocess.run(command + list(arguments), cwd=root, env=environment,
                                      capture_output=True, encoding="utf-8", check=True, timeout=20)

            run("reassign", "--channel", "direkte", "--competition-ref", "DEMO-FAG-COMP-001",
                "--person", "D-03", "--db", str(database))
            # Approve locally through the existing store, then prove startup does not undo it.
            approved = subprocess.run([str(interpreter), "-X", "utf8", "-c", "\n".join([
                "from pathlib import Path",
                "from mission_distribution.storage import DemoStore",
                "from mission_distribution.approval import review_revision",
                "from mission_distribution.models import Channel, load_direct_rules",
                "with DemoStore(Path('runtime/fagdemo.sqlite3')) as store:",
                "    task = next(t for t in store.tasks(Channel.DIRECT) if t['competition_ref']=='DEMO-FAG-COMP-001')",
                "    store.approve(task['task_id'], Channel.DIRECT, load_direct_rules(Path('demo_data/direct_rules.json')).people, review_revision(task, task['public_opportunity']))",
            ])], cwd=root, env=environment, capture_output=True, encoding="utf-8", timeout=20)
            self.assertEqual(approved.returncode, 0, approved.stderr)
            before = json.loads(run("tasks", "--channel", "direkte", "--db", str(database), "--json").stdout)["tasks"]
            again = subprocess.run(prepare, cwd=directory, env=environment, capture_output=True,
                                   encoding="utf-8", check=True, timeout=30)
            self.assertIn("allerede behandlet", again.stdout)
            after = json.loads(run("tasks", "--channel", "direkte", "--db", str(database), "--json").stdout)["tasks"]
            self.assertEqual(after, before)
            self.assertEqual(len(after), 6)

            probe = socket.socket()
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            probe.close()
            server = subprocess.Popen([sys.executable, "-X", "utf8", str(root / "start_demo.py"),
                                       "--no-browser", "--port", str(port)], cwd=directory, env=environment,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
            try:
                deadline = time.monotonic() + 30
                page = ""
                while time.monotonic() < deadline and server.poll() is None:
                    connection = HTTPConnection("127.0.0.1", port, timeout=1)
                    try:
                        connection.request("GET", "/")
                        response = connection.getresponse()
                        page = response.read().decode("utf-8")
                        if response.status == 200:
                            break
                    except OSError:
                        time.sleep(.1)
                    finally:
                        connection.close()
                self.assertIn("Oppdragsoversikt", page)
                self.assertIn("Godkjent lokalt", page)
                self.assertEqual(page.count('class="task-link"'), 6)
            finally:
                # Stop the wrapper gently so it can close its own child on Windows as well.
                if server.poll() is None and os.name == "nt":
                    # taskkill targets only the process tree started by this test.
                    subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True)
                elif server.poll() is None:
                    import signal
                    server.send_signal(signal.SIGINT)
                server.communicate(timeout=15)


if __name__ == "__main__":
    unittest.main()
