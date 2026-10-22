"""Generate synthetic source PDFs and one local example package."""

from pathlib import Path
import json
from zipfile import ZipFile

from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

from receipt_pack import build_pack


def create_receipt(path: Path, vendor: str, doc_date: str, amount: str, pages=1):
    canvas = Canvas(str(path), pagesize=(595, 842))
    for page in range(1, pages + 1):
        canvas.setFillColor(HexColor("#0f766e"))
        canvas.rect(0, 770, 595, 72, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#ffffff"))
        canvas.setFont("Helvetica-Bold", 19)
        canvas.drawString(44, 800, "SYNTHETIC RECEIPT - DEMO ONLY")
        canvas.setFillColor(HexColor("#182d36"))
        canvas.setFont("Helvetica-Bold", 23)
        canvas.drawString(44, 704, vendor)
        canvas.setFont("Helvetica", 14)
        canvas.drawString(44, 663, f"Document date: {doc_date}")
        canvas.drawString(44, 633, f"Reviewed total: EUR {amount}")
        canvas.drawString(44, 583, "This is a fictional fixture. No purchase took place.")
        canvas.drawString(44, 553, "Fields were supplied explicitly; OCR was not performed.")
        canvas.setFont("Helvetica", 11)
        canvas.drawString(44, 52, f"Source page {page} of {pages} | Keep this source unchanged")
        canvas.showPage()
    canvas.save()


def main():
    root = Path(__file__).parent
    fixtures = root / "fixtures"
    fixtures.mkdir(exist_ok=True)
    create_receipt(fixtures / "september.pdf", "Demo Stationery", "2026-09-30", "99.99")
    create_receipt(fixtures / "october-a.pdf", "Demo Supplies", "2026-10-01", "12.30", 2)
    create_receipt(fixtures / "october-b.pdf", "Demo Groceries", "2026-10-31", "7.07")
    create_receipt(fixtures / "november.pdf", "Demo Stationery", "2026-11-01", "80.00")
    records = [
        {"id": "sep", "date": "2026-09-30", "pdf": "september.pdf"},
        {"id": "oct-b", "date": "2026-10-31", "vendor": "Demo Groceries", "total": "7.07", "currency": "EUR", "category": "Food", "pdf": "october-b.pdf"},
        {"id": "oct-a", "date": "2026-10-01", "vendor": "Demo Supplies", "total": "12.30", "currency": "EUR", "category": "Supplies", "pdf": "october-a.pdf"},
        {"id": "nov", "date": "2026-11-01", "pdf": "november.pdf"},
    ]
    manifest = fixtures / "reviewed.json"
    manifest.write_text(json.dumps({"month": "2026-10", "expected_documents": 2, "documents": records}, indent=2) + "\n")
    output = root / "output/pdf"
    output.mkdir(parents=True, exist_ok=True)
    package = output / "synthetic-october-pack.zip"
    proof = build_pack(manifest, fixtures, package)
    with ZipFile(package) as archive:
        for name in archive.namelist():
            (output / name).write_bytes(archive.read(name))
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
