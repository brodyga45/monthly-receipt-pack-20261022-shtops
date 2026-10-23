"""Package reviewed local receipt metadata and PDFs. No network or OCR access."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader, PdfWriter


class PackError(ValueError):
    pass


def money(value: object) -> str:
    if not isinstance(value, str):
        raise PackError("total must be a decimal string")
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
            raise PackError("total must have at most two decimal places")
        return format(amount, ".2f")
    except InvalidOperation as exc:
        raise PackError("invalid total") from exc


def sheet_text(value: str) -> str:
    """Keep human-supplied text from becoming a spreadsheet formula."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def build_pack(manifest_path: Path, source_root: Path, output_zip: Path) -> dict:
    """Publish one new ZIP only after every selected input has been validated.

    The manifest's expected_documents is an external caller assertion. Matching
    it does not prove that a server-side query/export included every document.
    """
    source_root = source_root.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    month = manifest.get("month", "")
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise PackError("month must be YYYY-MM")
    date.fromisoformat(month + "-01")
    expected = manifest.get("expected_documents")
    if type(expected) is not int or expected < 1:
        raise PackError("expected_documents must be a positive integer")
    rows = manifest.get("documents")
    if not isinstance(rows, list):
        raise PackError("documents must be a list")

    selected = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("date"), str):
            raise PackError("every document needs an ISO document date")
        parsed_date = date.fromisoformat(row["date"])
        if parsed_date.isoformat() != row["date"]:
            raise PackError("date must be YYYY-MM-DD")
        if row["date"][:7] == month:
            selected.append(row)
    if len(selected) != expected:
        raise PackError(f"selected {len(selected)} documents; expected {expected}")
    ids = [r.get("id") for r in selected]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise PackError("selected document IDs must be non-empty unique strings")

    writer = PdfWriter()
    sources = []
    sheet_rows = []
    # Retain readers/bytes until writing; pypdf can resolve source objects lazily.
    readers = []
    for row in sorted(selected, key=lambda r: (r["date"], r["id"])):
        for key in ("vendor", "category", "pdf", "currency"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise PackError(f"document {row['id']}: missing {key}")
        if not re.fullmatch(r"[A-Z]{3}", row["currency"]):
            raise PackError("currency must be an uppercase three-letter code")
        amount = money(row.get("total"))
        relative = Path(row["pdf"])
        if relative.is_absolute() or ".." in relative.parts:
            raise PackError("PDF paths must stay inside source_root")
        path = (source_root / relative).resolve(strict=True)
        if not path.is_relative_to(source_root) or not path.is_file():
            raise PackError("PDF paths must stay inside source_root")
        data = path.read_bytes()
        reader = PdfReader(io.BytesIO(data), strict=True)
        readers.append(reader)
        if reader.is_encrypted or not len(reader.pages):
            raise PackError("selected PDFs must be unencrypted and non-empty")
        first = len(writer.pages) + 1
        for page in reader.pages:
            writer.add_page(page)
        last = len(writer.pages)
        sources.append({
            "id": row["id"], "source_file": row["pdf"],
            "sha256": hashlib.sha256(data).hexdigest(),
            "pages": len(reader.pages), "start_page": first, "end_page": last,
        })
        sheet_rows.append([
            sheet_text(row["vendor"]), row["date"], amount, row["currency"],
            sheet_text(row["category"]), sheet_text(row["id"]), first, last,
        ])

    pdf_stream = io.BytesIO()
    writer.write(pdf_stream)
    pdf = pdf_stream.getvalue()
    if len(PdfReader(io.BytesIO(pdf)).pages) != sum(s["pages"] for s in sources):
        raise PackError("merged PDF page count mismatch")
    csv_stream = io.StringIO(newline="")
    csv_writer = csv.writer(csv_stream)
    csv_writer.writerow([
        "vendor", "date", "total", "currency", "category", "document_id",
        "pdf_start_page", "pdf_end_page",
    ])
    csv_writer.writerows(sheet_rows)
    csv_bytes = csv_stream.getvalue().encode("utf-8-sig")
    proof = {
        "schema_version": 1, "month": month,
        "metadata_source": "reviewed local manifest; no extraction performed",
        "expected_documents": expected, "documents": len(sheet_rows),
        "pdf_pages": len(writer.pages), "order": "document date, then document ID",
        "pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(), "sources": sources,
    }
    output_zip = output_zip.absolute()
    if output_zip.exists():
        raise FileExistsError(output_zip)
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    # Stage in the same filesystem, then atomically link without replacing a file.
    with tempfile.TemporaryDirectory(dir=output_zip.parent) as temp:
        staged = Path(temp) / "pack.zip"
        with ZipFile(staged, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(f"{month}.csv", csv_bytes)
            archive.writestr(f"{month}.pdf", pdf)
            archive.writestr("manifest.json", json.dumps(proof, indent=2) + "\n")
        os.link(staged, output_zip)
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output_zip", type=Path)
    args = parser.parse_args()
    result = build_pack(args.manifest, args.source_root, args.output_zip)
    print(json.dumps({k: result[k] for k in ("month", "documents", "pdf_pages")}))


if __name__ == "__main__":
    main()
