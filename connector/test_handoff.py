"""A fictional HTTP archive exercises the actual CLI, transport and ZIP result."""
from contextlib import redirect_stderr, redirect_stdout
import copy
import csv
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

from pypdf import PdfReader
import monthly_handoff as app

ROOT = Path(__file__).parent
TOKEN = "fictional-api-token-for-local-tests-only"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, obj, status=200, content_type="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        state = self.server.state
        state["requests"].append(self.path)
        if self.headers.get("Authorization") != "Token " + TOKEN:
            return self.send({"detail": "bad token"}, 401)
        if state["mode"] == "auth_error":
            return self.send({"detail": "echoed " + TOKEN}, 403)
        path = urlsplit(self.path)
        if path.path == "/api/documents/":
            q = parse_qs(path.query)
            page = int(q.get("page", ["1"])[0])
            if page == 1:
                state["queries"].append(q)
            start = q.get("created__date__gte", [""])[0]
            end = q.get("created__date__lt", ["9999"])[0]
            tags = set(map(int, q.get("tags__id__all", [""])[0].split(","))) if q.get("tags__id__all") else set()
            docs = [copy.deepcopy(d) for d in state["docs"] if start <= d["created"][:10] < end and tags.issubset(d["tags"])]
            if state["mode"] == "mutate" and state["downloads"]:
                docs[-1]["modified"] = "2026-10-23T01:00:00Z"
            rows = docs[page-1:page]
            if page == 2 and state["mode"] == "duplicate":
                rows = docs[:1]
            if page == 2 and state["mode"] == "truncated":
                rows = []
            count = len(docs) + (1 if page == 2 and state["mode"] == "count_change" else 0)
            next_url = None
            if page < len(docs):
                from urllib.parse import urlencode
                next_q = dict(q, page=[str(page+1)])
                next_url = state["base"] + "/api/documents/?" + urlencode(next_q, doseq=True)
            if state["mode"] == "foreign_next":
                next_url = "https://not-the-instance.invalid/api/documents/?page=2"
            return self.send({"count": count, "next": next_url, "results": rows})
        if path.path.startswith("/api/custom_fields/"):
            fid = int(path.path.strip("/").split("/")[-1])
            return self.send({"id": fid, "data_type": "monetary" if fid == 7 else "string"})
        if path.path == "/api/correspondents/9/":
            name = "Changed supplier" if state["mode"] == "vendor_mutate" and state["downloads"] else "=Fictional Supplies"
            return self.send({"id": 9, "name": name})
        if path.path.endswith("/download/"):
            did = int(path.path.split("/")[3])
            state["downloads"] += 1
            if state["mode"] == "redirect_pdf":
                self.send_response(302)
                self.send_header("Location", state["base"].replace("127.0.0.1", "localhost") + "/must-not-receive-token")
                self.end_headers()
                return
            if state["mode"] == "broken_pdf":
                return self.send(b"%PDF-this-is-not-a-real-pdf", content_type="application/pdf")
            return self.send((ROOT / "fixtures" / state["files"][did]).read_bytes(), content_type="application/pdf")
        return self.send({}, 404)


class HandoffIntegration(unittest.TestCase):
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
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "october.zip"
        base = "http://127.0.0.1:" + str(self.server.server_port)
        docs = []
        for did, created, amount in [(1,"2026-09-30","EUR8.00"),(2,"2026-10-01","EUR12.30"),(3,"2026-10-31","EUR7.07"),(4,"2026-11-01","EUR9.00")]:
            docs.append({"id": did,"created":created,"modified":"2026-10-22T00:00:00Z","root_document":None,"mime_type":"application/pdf","tags":[5],"correspondent":9,"custom_fields":[{"field":7,"value":amount},{"field":8,"value":"Supplies" if did == 2 else "Food"}]})
        self.state = {"base":base,"mode":"normal","docs":docs,"files":{2:"october-a.pdf",3:"october-b.pdf"},"requests":[],"queries":[],"downloads":0}
        self.server.state = self.state

    def run_cli(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        args = ["2026-10", str(self.output), "--total-field", "7", "--category-field", "8", *extra]
        with patch.dict(os.environ, {"PAPERLESS_URL":self.state["base"],"PAPERLESS_TOKEN":TOKEN}), redirect_stdout(out), redirect_stderr(err):
            code = app.main(args)
        self.assertNotIn(TOKEN, out.getvalue()+err.getvalue())
        return code, out.getvalue(), err.getvalue()

    def test_month_to_checked_sheet_pdf_and_selection(self):
        code, out, err = self.run_cli("--tag-id", "5")
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        self.assertEqual((result["documents"],result["pdf_pages"]), (2,3))
        with ZipFile(self.output) as z:
            self.assertEqual(set(z.namelist()), {"2026-10.csv","2026-10.pdf","manifest.json","selection.json"})
            rows = list(csv.DictReader(io.StringIO(z.read("2026-10.csv").decode("utf-8-sig"))))
            self.assertEqual([(x["date"],x["total"],x["currency"],x["pdf_start_page"],x["pdf_end_page"]) for x in rows], [("2026-10-01","12.30","EUR","1","2"),("2026-10-31","7.07","EUR","3","3")])
            self.assertEqual(rows[0]["vendor"], "'=Fictional Supplies")
            pdf = z.read("2026-10.pdf")
            self.assertEqual(len(PdfReader(io.BytesIO(pdf)).pages), 3)
            manifest = json.loads(z.read("manifest.json"))
            self.assertEqual(manifest["pdf_sha256"], hashlib.sha256(pdf).hexdigest())
            for src in manifest["sources"]:
                data = (ROOT/"fixtures"/self.state["files"][int(src["id"])]).read_bytes()
                self.assertEqual(src["sha256"], hashlib.sha256(data).hexdigest())
            selection = json.loads(z.read("selection.json"))
            self.assertEqual(selection["selected_document_ids"], [2,3])
            self.assertEqual(selection["api_documents"], 2)
            self.assertNotIn(TOKEN.encode(), b"".join(z.read(n) for n in z.namelist()))
        self.assertEqual(len(self.state["queries"]), 2)
        self.assertTrue(all(q["tags__id__all"] == ["5"] for q in self.state["queries"]))

    def test_exact_large_monetary_string(self):
        self.state["docs"][1]["custom_fields"][0]["value"] = "RSD9007199254740993.99"
        code, _, err = self.run_cli()
        self.assertEqual(code, 0, err)
        with ZipFile(self.output) as z:
            self.assertIn(b"9007199254740993.99,RSD", z.read("2026-10.csv"))

    def test_refusals_publish_no_zip(self):
        for mode in ["count_change","duplicate","truncated","foreign_next","mutate","vendor_mutate","broken_pdf","redirect_pdf","auth_error"]:
            with self.subTest(mode=mode):
                self.state.update(mode=mode, requests=[], queries=[], downloads=0)
                code, _, err = self.run_cli()
                self.assertEqual(code, 1, (mode,err))
                self.assertFalse(self.output.exists(), mode)
                self.assertFalse(list(self.output.parent.glob("monthly-handoff-*")))
                self.assertFalse(any("must-not-receive-token" in x for x in self.state["requests"]))

    def test_missing_reviewed_value_stops_before_download(self):
        self.state["docs"][1]["custom_fields"][0]["value"] = None
        code, _, err = self.run_cli()
        self.assertEqual(code, 1, err)
        self.assertEqual(self.state["downloads"], 0)
        self.assertFalse(self.output.exists())

    def test_empty_filter_reports_no_artifact(self):
        code, out, err = self.run_cli("--tag-id", "6")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out), {"month":"2026-10","documents":0,"output":None})
        self.assertFalse(self.output.exists())

    def test_limits_and_existing_output(self):
        for flags in [("--max-documents","1"),("--max-pdf-bytes","10"),("--max-total-bytes","10")]:
            with self.subTest(flags=flags):
                code, _, err = self.run_cli(*flags)
                self.assertEqual(code, 1, err)
                self.assertFalse(self.output.exists())
        self.output.write_bytes(b"existing-owner-file")
        self.state["requests"].clear()
        code, _, err = self.run_cli()
        self.assertEqual(code, 1, err)
        self.assertEqual(self.output.read_bytes(), b"existing-owner-file")
        self.assertEqual(self.state["requests"], [])


if __name__ == "__main__":
    unittest.main()
