"""Exercise local-model boundaries with explicit simulated responses, not real AI."""

from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler
from io import StringIO
import json
from threading import Thread
import unittest
from unittest.mock import patch

from mission_distribution import phi_review as phi
from mission_distribution.storage import DemoStore
from mission_distribution.web_server import LocalDemoServer


def simulated_answer(case):
    # Deliberately simulated. This fixture must never be used as a model-quality result.
    return {trade: {"status": "uklart", "sitat": ""} for trade in sorted(phi.TRADES)}


def envelope(case):
    return {"model": phi.MODEL, "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(simulated_answer(case))}}


class PhiValidationTests(unittest.TestCase):
    def setUp(self):
        self.definitions, examples = phi.load_examples()
        self.case = examples[0][0]

    def test_examples_cover_negation_multitrade_missing_text_and_cpv_disagreement(self):
        _, examples = phi.load_examples()
        self.assertEqual(len(examples), 8)
        self.assertEqual(examples[1][1]["FS"], "inngår_ikke")
        self.assertEqual(examples[3][1]["FS"], "inngår")
        self.assertEqual(examples[3][1]["SE"], "inngår")
        self.assertEqual(set(examples[4][1].values()), {"uklart"})
        self.assertEqual(examples[-1][0].main_cpv, "50700000")
        self.assertEqual(examples[-1][1]["BA"], "inngår_ikke")

    def test_literal_support_is_required_and_fabricated_quotes_are_rejected(self):
        answer = simulated_answer(self.case)
        answer["FS"] = {"status": "inngår", "sitat": "brannalarmanlegg"}
        self.assertEqual(phi.validate_assessment(answer, self.case), answer)
        for quote in ("", "Dette sitatet finnes ikke"):
            with self.subTest(quote=quote), self.assertRaises(phi.PhiReviewError):
                answer["FS"]["sitat"] = quote
                phi.validate_assessment(answer, self.case)

    def test_unknown_tags_statuses_and_confidence_fields_are_rejected(self):
        for change in ("tag", "status", "confidence", "missing"):
            answer = simulated_answer(self.case)
            if change == "tag":
                answer["OTHER"] = {"status": "uklart", "sitat": ""}
            elif change == "status":
                answer["FS"]["status"] = "kanskje"
            elif change == "confidence":
                answer["FS"]["confidence"] = .99
            else:
                del answer["BA"]
            with self.subTest(change=change), self.assertRaises(phi.PhiReviewError):
                phi.validate_assessment(answer, self.case)

    def test_duplicate_json_fields_are_rejected(self):
        with self.assertRaises(phi.PhiReviewError):
            phi._json('{"FS": {}, "FS": {}}')

    def test_request_contains_only_fictional_text_and_demo_definitions(self):
        with patch.object(phi, "local_request", return_value=envelope(self.case)) as request:
            phi.review_case(self.case, self.definitions)
        path, payload = request.call_args.args
        self.assertEqual(path, "/api/chat")
        self.assertEqual(payload["model"], "phi4-mini:3.8b")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"]["num_ctx"], 4096)
        state = json.loads(payload["messages"][1]["content"])
        self.assertEqual(set(state), {"synthetic", "title", "description", "demo_trade_definitions"})
        self.assertTrue(state["synthetic"])
        self.assertNotIn("expected", json.dumps(payload))
        self.assertNotIn("main_cpv", state)

    def test_truncated_wrong_model_or_tool_call_response_is_rejected(self):
        for change in ("truncated", "wrong_model", "tool_call", "wrong_role"):
            response = envelope(self.case)
            if change == "truncated":
                response["done_reason"] = "length"
            elif change == "wrong_model":
                response["model"] = "other:cloud"
            elif change == "tool_call":
                response["message"]["tool_calls"] = [{"function": {"name": "assign"}}]
            else:
                response["message"]["role"] = "user"
            with self.subTest(change=change), patch.object(phi, "local_request", return_value=response):
                with self.assertRaises(phi.PhiReviewError):
                    phi.review_case(self.case, self.definitions)

    def test_model_check_does_not_trigger_generation_or_download(self):
        response = {"models": [{"name": phi.MODEL, "digest": "demo-digest"}]}
        with patch.object(phi, "local_request", return_value=response) as request:
            self.assertEqual(phi.check_model(), "demo-digest")
        request.assert_called_once_with("/api/tags", timeout=5)
        with patch.object(phi, "local_request", return_value={"models": []}):
            with self.assertRaisesRegex(phi.PhiReviewError, "ollama pull"):
                phi.check_model()

    def test_check_json_has_no_simulated_assessment(self):
        output = StringIO()
        with patch.object(phi, "check_model", return_value="demo-digest"), redirect_stdout(output):
            self.assertEqual(phi.main(["--check", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["results"], [])

    def test_invalid_model_answer_is_visible_without_opening_a_database(self):
        output = StringIO()
        with (patch.object(phi, "check_model", return_value="demo-digest"),
              patch.object(phi, "review_case", side_effect=phi.PhiReviewError("Simulert feil")),
              patch.object(DemoStore, "__init__", side_effect=AssertionError("Must not open storage")) as storage,
              redirect_stdout(output), redirect_stderr(StringIO())):
            self.assertEqual(phi.main(["--json"]), 1)
            storage.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertFalse(report["assignment_rules_changed"])
        self.assertIn("error", report["results"][0])
        self.assertNotIn("assessment", report["results"][0])

    def test_rejected_answer_is_available_only_with_explicit_diagnostics_and_never_scored(self):
        response = envelope(self.case)
        answer = simulated_answer(self.case)
        answer["BA"] = {"status": "inngår", "sitat": self.definitions["BA"]}
        raw = json.dumps(answer, ensure_ascii=False)
        response["message"]["content"] = raw
        for diagnostics in (False, True):
            output = StringIO()
            arguments = ["--json"] + (["--diagnostics"] if diagnostics else [])
            with (patch.object(phi, "check_model", return_value="simulated-digest"),
                  patch.object(phi, "local_request", return_value=response),
                  redirect_stdout(output), redirect_stderr(StringIO())):
                self.assertEqual(phi.main(arguments), 1)
            report = json.loads(output.getvalue())
            self.assertEqual(report["summary"], {"attempted": 1, "valid": 0, "rejected": 1})
            item = report["results"][0]
            self.assertNotIn("assessment", item)
            self.assertNotIn("matching_demo_statuses", item)
            self.assertEqual("diagnostics" in item, diagnostics)
            if diagnostics:
                self.assertEqual(item["diagnostics"]["model_content"], raw)
                self.assertEqual(len(item["diagnostics"]["request_fingerprint"]), 64)

    def test_terminal_diagnostics_escape_control_characters_in_rejected_model_text(self):
        response = envelope(self.case)
        answer = simulated_answer(self.case)
        answer["BA"] = {"status": "inngår", "sitat": "Not a quote \x1b[31m"}
        response["message"]["content"] = json.dumps(answer)
        output = StringIO()
        with (patch.object(phi, "check_model", return_value="simulated-digest"),
              patch.object(phi, "local_request", return_value=response),
              redirect_stdout(output), redirect_stderr(StringIO())):
            self.assertEqual(phi.main(["--diagnostics"]), 1)
        self.assertIn("AVVIST", output.getvalue())
        self.assertNotIn("\x1b", output.getvalue())
        self.assertIn("\\u001b", output.getvalue())

    def test_invalid_json_is_preserved_for_diagnostics_without_becoming_an_assessment(self):
        response = envelope(self.case)
        response["message"]["content"] = "This is not JSON"
        with patch.object(phi, "local_request", return_value=response):
            with self.assertRaises(phi.PhiReviewError) as error:
                phi.review_case(self.case, self.definitions)
        self.assertEqual(error.exception.diagnostics["model_content"], "This is not JSON")


class LocalOllamaTransportTests(unittest.TestCase):
    def test_real_loopback_http_exchange_uses_fixed_model_and_validates_simulated_reply(self):
        definitions, examples = phi.load_examples()
        case = examples[0][0]
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                self.reply({"models": [{"name": phi.MODEL, "digest": "simulated-digest"}]})

            def do_POST(self):
                received.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                self.reply(envelope(case))

            def reply(self, body):
                body = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = LocalDemoServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        try:
            with patch.object(phi, "PORT", server.server_port):
                self.assertEqual(phi.check_model(), "simulated-digest")
                result = phi.review_case(case, definitions)
            self.assertEqual(set(result["assessment"]), phi.TRADES)
            self.assertEqual(received[0], "/api/tags")
            self.assertEqual(received[1][0], "/api/chat")
            self.assertEqual(received[1][1]["model"], phi.MODEL)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_connection_failure_has_actionable_error(self):
        with patch.object(phi, "HTTPConnection") as connection:
            connection.return_value.request.side_effect = ConnectionRefusedError()
            with self.assertRaisesRegex(phi.PhiReviewError, "Åpne Ollama"):
                phi.check_model()
            self.assertEqual(connection.call_args.args, ("127.0.0.1", 11434))
            connection.return_value.close.assert_called_once()

    def test_redirects_and_oversized_responses_are_not_followed(self):
        for status, raw in ((302, b"{}"), (200, b"x" * (phi.MAX_RESPONSE + 1))):
            with self.subTest(status=status), patch.object(phi, "HTTPConnection") as connection:
                response = connection.return_value.getresponse.return_value
                response.status = status
                response.read.return_value = raw
                with self.assertRaises(phi.PhiReviewError):
                    phi.check_model()
                self.assertEqual(connection.return_value.request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
