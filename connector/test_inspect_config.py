"""Authenticated loopback HTTP checks for metadata-only configuration discovery."""
from contextlib import redirect_stderr, redirect_stdout
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import inspect_config as app

TOKEN = "fictional-inspection-token-not-a-credential"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        state = self.server.state
        state["requests"].append((self.command, self.path))
        path = urlsplit(self.path)
        if state["mode"] == "redirect_documents" and path.path == "/api/custom_fields/":
            self.send_response(302)
            self.send_header("Location", state["base"] + "/api/documents/")
            self.end_headers()
            return
        status = 200
        if self.headers.get("Authorization") != "Token " + TOKEN:
            payload, status = {"detail": "unauthorised"}, 401
        elif state["mode"] == "denied":
            payload, status = {"detail": "echoed " + TOKEN}, 403
        elif path.path not in state["collections"]:
            payload, status = {"detail": "not a metadata endpoint"}, 404
        else:
            rows = copy.deepcopy(state["collections"][path.path])
            page = int(parse_qs(path.query).get("page", ["1"])[0])
            result = rows[page - 1:page]
            nxt = state["base"] + path.path + "?page=" + str(page + 1) if page < len(rows) else None
            count = len(rows)
            if page == 1 and state["mode"] == "foreign":
                nxt = "https://not-the-instance.invalid/api/custom_fields/?page=2"
            if page == 1 and state["mode"] == "wrong_endpoint":
                nxt = state["base"] + "/api/documents/?page=2"
            if page == 2 and state["mode"] == "duplicate":
                result = rows[:1]
            if page == 2 and state["mode"] == "count_change":
                count += 1
            if page == 2 and state["mode"] == "truncated":
                result, nxt = [], None
            if page == 1 and state["mode"] == "too_many":
                count = 1001
            payload = {"count": count, "results": result, "next": nxt}
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class InspectIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.state = {"mode": "normal", "base": "http://127.0.0.1:" + str(self.server.server_port),
                      "requests": [], "collections": {
                          "/api/custom_fields/": [{"id": 7, "name": "Reviewed total", "data_type": "monetary"},
                                                  {"id": 8, "name": "Reviewed category", "data_type": "string"},
                                                  {"id": 9, "name": "Unrelated number", "data_type": "float"}],
                          "/api/tags/": [{"id": 5, "name": "Receipts"}, {"id": 6, "name": "Draft"}]}}
        self.server.state = self.state

    def run_cli(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"PAPERLESS_URL": self.state["base"], "PAPERLESS_TOKEN": TOKEN}), redirect_stdout(out), redirect_stderr(err):
            code = app.main([])
        self.assertNotIn(TOKEN, out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def test_paginated_fields_tags_only_and_no_automatic_mapping(self):
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual([(x["id"], x["usable_as"]) for x in data["fields"]],
                         [(7, "total candidate"), (8, "category candidate"), (9, "unsupported by this connector")])
        self.assertEqual([x["id"] for x in data["tags"]], [5, 6])
        self.assertFalse(data["document_contents_read"])
        self.assertFalse(data["archive_modified"])
        self.assertEqual(len(self.state["requests"]), 5)
        self.assertTrue(all(method == "GET" and urlsplit(url).path in self.state["collections"]
                            for method, url in self.state["requests"]))
        self.assertNotIn(self.state["base"], out)

    def test_refusals_emit_no_partial_configuration(self):
        for mode in ["foreign", "wrong_endpoint", "duplicate", "count_change", "truncated", "too_many", "denied"]:
            with self.subTest(mode=mode):
                self.state.update(mode=mode, requests=[])
                code, out, err = self.run_cli()
                self.assertEqual(code, 1, (mode, err))
                self.assertEqual(out, "")
                self.assertFalse(any("documents" in p for _, p in self.state["requests"]))

    def test_zero_fields_and_zero_tags_remain_an_explicit_empty_listing(self):
        self.state["collections"] = {"/api/custom_fields/": [], "/api/tags/": []}
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual((data["fields"], data["tags"]), ([], []))

    def test_echoed_token_in_metadata_is_redacted(self):
        self.state["collections"]["/api/tags/"][0]["name"] = "Unexpected " + TOKEN
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertIn("[REDACTED]", out)

    def test_same_origin_redirect_is_refused_before_document_request(self):
        self.state["mode"] = "redirect_documents"
        code, out, err = self.run_cli()
        self.assertEqual(code, 1, err)
        self.assertEqual(out, "")
        self.assertIn("metadata redirects are not followed", err)
        self.assertEqual(self.state["requests"], [("GET", "/api/custom_fields/?page_size=100")])


if __name__ == "__main__":
    unittest.main()
