"""Read reviewed Paperless fields and original PDFs into a monthly handoff ZIP."""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from zipfile import ZipFile
from pypdf.errors import PdfReadError

from receipt_pack import PackError, build_pack, money
from vendor import paperless_export as upstream


class HandoffError(ValueError):
    pass


def month_bounds(month):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HandoffError("month must be YYYY-MM")
    start = date.fromisoformat(month + "-01")
    if start.year == 9999 and start.month == 12:
        raise HandoffError("month must be earlier than 9999-12")
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def positive_id(value):
    if type(value) is not int or value < 1:
        raise HandoffError("document and field IDs must be positive integers")
    return value


def document_date(value):
    if not isinstance(value, str):
        raise HandoffError("document has no valid created date")
    if len(value) == 10:
        return date.fromisoformat(value).isoformat()
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()


def select_documents(client, month, tag_ids, limit):
    start, end = month_bounds(month)
    params = {"created__date__gte": start, "created__date__lt": end,
              "ordering": "created,id", "page_size": "100", "truncate_content": "true"}
    if tag_ids:
        params["tags__id__all"] = ",".join(str(positive_id(x)) for x in tag_ids)
    path, seen, docs, expected = "/api/documents/", set(), [], None
    prefix = urllib.parse.urlsplit(client.base).path.rstrip("/")
    while path:
        if path in seen:
            raise HandoffError("pagination repeated a page; no package created")
        seen.add(path)
        page, _ = client.get(path, params if len(seen) == 1 else None)
        if not isinstance(page, dict) or type(page.get("count")) is not int:
            raise HandoffError("API page has no valid document count")
        count = page["count"]
        if not 0 <= count <= limit:
            raise HandoffError("selection exceeds the document limit or has an invalid count")
        if expected is None:
            expected = count
        if count != expected:
            raise HandoffError("document count changed during pagination; retry when quiet")
        rows = page.get("results")
        if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
            raise HandoffError("API results must be document objects")
        docs.extend(rows)
        if len(docs) > expected:
            raise HandoffError("API pages contain more documents than their count")
        nxt = page.get("next")
        if nxt and not rows:
            raise HandoffError("empty API page points to another page")
        if nxt is None:
            path = None
        elif not isinstance(nxt, str) or not nxt:
            raise HandoffError("invalid pagination link")
        else:
            path = client.next_path(nxt)
            parsed = urllib.parse.urlsplit(path)
            if parsed.path != prefix + "/api/documents/":
                raise HandoffError("pagination left the document-list endpoint")
            path = urllib.parse.urlunsplit(("", "", "/api/documents/", parsed.query, ""))
    if len(docs) != expected:
        raise HandoffError("API document count does not match the collected rows")
    ids = [positive_id(x.get("id")) for x in docs]
    if len(set(ids)) != len(ids):
        raise HandoffError("duplicate document ID across API pages")
    for row in docs:
        if row.get("root_document") is not None:
            raise HandoffError("a document version was returned instead of a root document")
        if document_date(row.get("created"))[:7] != month:
            raise HandoffError("API returned a document outside the requested month")
        if not set(tag_ids).issubset(row.get("tags") or []):
            raise HandoffError("API returned a document outside the requested tags")
    return sorted(docs, key=lambda x: x["id"]), params


def normalize(client, docs, total_field, category_field):
    fields = {}
    for fid in [positive_id(total_field), positive_id(category_field)]:
        fields[fid], _ = client.get(f"/api/custom_fields/{fid}/")
        if not isinstance(fields[fid], dict) or fields[fid].get("id") != fid:
            raise HandoffError("API returned an unexpected custom-field definition")
    if fields[total_field].get("data_type") != "monetary":
        raise HandoffError("total field must be a Paperless monetary field")
    if fields[category_field].get("data_type") != "string":
        raise HandoffError("category field must be a Paperless text field")
    vendors, result = {}, []
    for doc in docs:
        did = positive_id(doc["id"])
        if doc.get("mime_type") != "application/pdf":
            raise HandoffError(f"document {did}: original must be a PDF")
        values = {}
        for item in doc.get("custom_fields") or []:
            if not isinstance(item, dict) or item.get("field") in values:
                raise HandoffError(f"document {did}: invalid or duplicate custom field")
            values[item.get("field")] = item.get("value")
        raw = values.get(total_field)
        match = re.fullmatch(r"([A-Z]{3})\s?(-?\d+(?:\.\d{1,2})?)", raw.strip()) if isinstance(raw, str) else None
        if not match:
            raise HandoffError(f"document {did}: reviewed monetary value must include currency and decimal amount")
        category = values.get(category_field)
        if not isinstance(category, str) or not category.strip():
            raise HandoffError(f"document {did}: missing reviewed category")
        cid = positive_id(doc.get("correspondent"))
        if cid not in vendors:
            supplier, _ = client.get(f"/api/correspondents/{cid}/")
            if not isinstance(supplier, dict) or supplier.get("id") != cid:
                raise HandoffError(f"document {did}: unexpected correspondent response")
            vendors[cid] = supplier.get("name")
        if not isinstance(vendors[cid], str) or not vendors[cid].strip():
            raise HandoffError(f"document {did}: missing correspondent name")
        result.append({"id": str(did), "date": document_date(doc["created"]),
                       "vendor": vendors[cid], "total": money(match[2]),
                       "currency": match[1], "category": category,
                       "pdf": str(did) + ".pdf"})
    return result


def download_original(client, did, max_bytes):
    request = urllib.request.Request(
        client.base + f"/api/documents/{positive_id(did)}/download/?original=true",
        headers={"Authorization": "Token " + client.token})
    try:
        with client.opener.open(request, timeout=upstream.TIMEOUT) as response:
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as error:
        raise HandoffError(f"document {did}: download returned HTTP {error.code}") from None
    if len(data) > max_bytes:
        raise HandoffError(f"document {did}: PDF exceeds the configured byte limit")
    if not data.startswith(b"%PDF-"):
        raise HandoffError(f"document {did}: download is not a PDF")
    return data


def fingerprint(docs):
    # Two reads catch observed drift, not an atomic server snapshot.
    return [{k: x.get(k) for k in ("id", "created", "modified", "correspondent",
                                  "custom_fields", "mime_type", "root_document", "tags")}
            for x in docs]


def handoff(client, month, total_field, category_field, output, tag_ids=(),
            max_documents=500, max_pdf_bytes=25_000_000, max_total_bytes=250_000_000):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise HandoffError("output exists; choose a new ZIP filename")
    positive_id(total_field)
    positive_id(category_field)
    if total_field == category_field:
        raise HandoffError("total and category must use different fields")
    if any(type(x) is not int or x < 1 for x in [max_documents, max_pdf_bytes, max_total_bytes]):
        raise HandoffError("resource limits must be positive integers")
    docs, params = select_documents(client, month, tag_ids, max_documents)
    if not docs:
        return {"month": month, "documents": 0, "output": None}
    rows = normalize(client, docs, total_field, category_field)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="monthly-handoff-", dir=output.parent) as tmp:
        root = Path(tmp)
        downloaded = 0
        for row in rows:
            data = download_original(client, int(row["id"]), min(max_pdf_bytes, max_total_bytes - downloaded))
            downloaded += len(data)
            (root / row["pdf"]).write_bytes(data)
        after, _ = select_documents(client, month, tag_ids, max_documents)
        if fingerprint(after) != fingerprint(docs):
            raise HandoffError("selected documents changed during download; retry when quiet")
        if normalize(client, after, total_field, category_field) != rows:
            raise HandoffError("field definitions or correspondent names changed during download")
        manifest = {"month": month, "expected_documents": len(rows), "documents": rows}
        manifest_path = root / "reviewed-input.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        staged = root / "handoff.zip"
        proof = build_pack(manifest_path, root, staged)
        receipt = {"month": month, "query": params, "api_documents": len(docs),
                   "selected_document_ids": [x["id"] for x in docs],
                   "total_field_id": total_field, "category_field_id": category_field,
                   "pdf_version": "original", "downloaded_bytes": downloaded,
                   "selection_rechecked_after_download": True,
                   "limits": "Two reads matched; not an atomic snapshot or proof of accounting completeness. Metadata supplied by the archive, not extracted or certified."}
        with ZipFile(staged, "a") as archive:
            archive.writestr("selection.json", json.dumps(receipt, indent=2) + "\n")
        os.link(staged, output)
    return {"month": month, "documents": proof["documents"], "pdf_pages": proof["pdf_pages"], "output": str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("month")
    parser.add_argument("output_zip", type=Path)
    parser.add_argument("--total-field", type=int, required=True)
    parser.add_argument("--category-field", type=int, required=True)
    parser.add_argument("--tag-id", type=int, action="append", default=[])
    parser.add_argument("--max-documents", type=int, default=500)
    parser.add_argument("--max-pdf-bytes", type=int, default=25_000_000)
    parser.add_argument("--max-total-bytes", type=int, default=250_000_000)
    args = parser.parse_args(argv)
    token = os.environ.get("PAPERLESS_TOKEN", "").strip()
    try:
        if not token or any(c.isspace() for c in token):
            raise HandoffError("set PAPERLESS_TOKEN to an existing authorised API token")
        raw = os.environ.get("PAPERLESS_URL", "")
        if urllib.parse.urlsplit(raw).username is not None:
            raise HandoffError("PAPERLESS_URL must not contain credentials")
        base = upstream.check_url(raw, insecure=False)
        client = upstream.Client(base, token)
        result = handoff(client, args.month, args.total_field, args.category_field,
                         args.output_zip, args.tag_id, args.max_documents,
                         args.max_pdf_bytes, args.max_total_bytes)
        print(json.dumps(result))
        return 0
    except (HandoffError, PackError, PdfReadError, upstream.ExportError, upstream.UsageError,
            ValueError, OSError, KeyError, TypeError) as error:
        message = str(error).replace(token, "[REDACTED]") if token else str(error)
        print("Handoff failed: " + message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; inspect the output filename before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
