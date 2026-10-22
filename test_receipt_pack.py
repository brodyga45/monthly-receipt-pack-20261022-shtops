import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from receipt_pack import PackError, build_pack


class ReceiptPackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root / "reviewed.json"
        self.out = self.root / "result.zip"
        for filename, label in [("a.pdf", "First October page"), ("b.pdf", "Last October page")]:
            c = Canvas(str(self.root / filename), pagesize=(300, 400))
            c.drawString(20, 350, label)
            if filename == "a.pdf":
                c.showPage()
                c.drawString(20, 350, "Second page of first receipt")
            c.save()
        self.rows = [self.row("b", "2026-10-31", "b.pdf", "7.07"), self.row("a", "2026-10-01", "a.pdf", "12.30")]

    @staticmethod
    def row(doc_id, day, pdf, total):
        return {"id": doc_id, "date": day, "pdf": pdf, "vendor": "Fixture Vendor", "total": total, "currency": "EUR", "category": "Supplies"}

    def run_pack(self, rows=None, expected=2):
        self.manifest.write_text(json.dumps({"month": "2026-10", "expected_documents": expected, "documents": self.rows if rows is None else rows}))
        return build_pack(self.manifest, self.root, self.out)

    def test_month_boundaries_order_pages_money_and_source_preservation(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.glob("*.pdf")}
        rows = self.rows + [self.row("sep", "2026-09-30", "nonexistent.pdf", "1.00"), self.row("nov", "2026-11-01", "nonexistent.pdf", "2.00")]
        proof = self.run_pack(rows)
        with ZipFile(self.out) as z:
            pdf = z.read("2026-10.pdf")
            sheet = list(csv.DictReader(io.StringIO(z.read("2026-10.csv").decode("utf-8-sig"))))
            pages = PdfReader(io.BytesIO(pdf)).pages
            self.assertEqual([p.extract_text().strip() for p in pages], ["First October page", "Second page of first receipt", "Last October page"])
            self.assertEqual([r["total"] for r in sheet], ["12.30", "7.07"])
            self.assertEqual([(r["pdf_start_page"], r["pdf_end_page"]) for r in sheet], [("1", "2"), ("3", "3")])
            self.assertEqual(len(sheet), proof["expected_documents"])
            self.assertEqual(hashlib.sha256(pdf).hexdigest(), proof["pdf_sha256"])
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.glob("*.pdf")})

    def test_missing_pdf_publishes_no_package(self):
        self.rows[1]["pdf"] = "missing.pdf"
        with self.assertRaises(FileNotFoundError):
            self.run_pack()
        self.assertFalse(self.out.exists())

    def test_duplicate_document_ids_rejected(self):
        self.rows[1]["id"] = "b"
        with self.assertRaises(PackError):
            self.run_pack()

    def test_count_mismatch_rejected(self):
        with self.assertRaises(PackError):
            self.run_pack(expected=3)

    def test_imprecise_or_missing_totals_are_not_silently_rounded(self):
        for value in ("12.345", "NaN", "Infinity", None, 7.07):
            with self.subTest(value=value):
                self.rows[0]["total"] = value
                with self.assertRaises(PackError):
                    self.run_pack()
                self.assertFalse(self.out.exists())

    def test_source_path_escape_rejected(self):
        self.rows[0]["pdf"] = "../outside.pdf"
        with self.assertRaises(PackError):
            self.run_pack()

    def test_encrypted_pdf_rejected(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=400)
        writer.encrypt("fixture-password")
        writer.write(self.root / "locked.pdf")
        self.rows[0]["pdf"] = "locked.pdf"
        with self.assertRaises(PackError):
            self.run_pack()
        self.assertFalse(self.out.exists())

    def test_existing_output_preserved(self):
        self.out.write_bytes(b"existing output")
        with self.assertRaises(FileExistsError):
            self.run_pack()
        self.assertEqual(self.out.read_bytes(), b"existing output")

    def test_csv_formula_text_escaped(self):
        self.rows[0]["vendor"] = " =1+1"
        self.run_pack()
        with ZipFile(self.out) as z:
            sheet = list(csv.DictReader(io.StringIO(z.read("2026-10.csv").decode("utf-8-sig"))))
        self.assertEqual(sheet[1]["vendor"], "' =1+1")


if __name__ == "__main__":
    unittest.main()
