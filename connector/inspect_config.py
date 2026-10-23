"""List Paperless field/tag IDs for a human-selected monthly handoff mapping."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

from vendor import paperless_export as upstream


class InspectionError(ValueError):
    pass


class NoMetadataRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise InspectionError("metadata redirects are not followed; use the canonical PAPERLESS_URL")


class MetadataClient(upstream.Client):
    def __init__(self, base, token):
        super().__init__(base, token)
        # Even same-origin redirects could leave the two permitted collections.
        self.opener = urllib.request.build_opener(NoMetadataRedirects)


def read_definitions(client, endpoint, limit=1000):
    """Read only this collection, refusing incomplete or drifting pagination."""
    path, seen, items, expected = endpoint, set(), [], None
    prefix = urllib.parse.urlsplit(client.base).path.rstrip("/")
    while path:
        if path in seen:
            raise InspectionError("metadata pagination repeated a page")
        seen.add(path)
        page, _ = client.get(path, {"page_size": "100"} if len(seen) == 1 else None)
        if not isinstance(page, dict) or type(page.get("count")) is not int:
            raise InspectionError("metadata page has no valid count")
        count = page["count"]
        if not 0 <= count <= limit:
            raise InspectionError("metadata count exceeds the limit or is invalid")
        if expected is None:
            expected = count
        if count != expected:
            raise InspectionError("metadata count changed; retry when the archive is quiet")
        rows = page.get("results")
        if not isinstance(rows, list) or any(not isinstance(x, dict) for x in rows):
            raise InspectionError("metadata results must be objects")
        items.extend(rows)
        if len(items) > expected:
            raise InspectionError("metadata contains more items than its count")
        nxt = page.get("next")
        if nxt is None:
            path = None
        elif not isinstance(nxt, str) or not nxt or not rows:
            raise InspectionError("invalid metadata pagination link or empty intermediate page")
        else:
            parsed = urllib.parse.urlsplit(client.next_path(nxt))
            if parsed.path != prefix + endpoint:
                raise InspectionError("pagination left the selected metadata endpoint")
            path = urllib.parse.urlunsplit(("", "", endpoint, parsed.query, ""))
    if len(items) != expected:
        raise InspectionError("metadata count does not match collected items")
    ids = [x.get("id") for x in items]
    if any(type(x) is not int or x < 1 for x in ids) or len(set(ids)) != len(ids):
        raise InspectionError("invalid or duplicate metadata ID")
    if any(not isinstance(x.get("name"), str) or not x["name"].strip() for x in items):
        raise InspectionError("metadata item has no valid name")
    return sorted(items, key=lambda x: x["id"])


def inspect_config(client):
    fields = read_definitions(client, "/api/custom_fields/")
    tags = read_definitions(client, "/api/tags/")
    for field in fields:
        if not isinstance(field.get("data_type"), str) or not field["data_type"]:
            raise InspectionError("field has no valid data type")
    roles = {"monetary": "total candidate", "string": "category candidate"}
    return {
        "fields": [{"id": x["id"], "name": x["name"], "type": x["data_type"],
                    "usable_as": roles.get(x["data_type"], "unsupported by this connector")}
                   for x in fields],
        "tags": [{"id": x["id"], "name": x["name"]} for x in tags],
        "selection": "Choose the correct reviewed total/category fields and receipt tags yourself. Type alone does not establish meaning or reviewed values.",
        "document_contents_read": False,
        "archive_modified": False,
    }


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    token = os.environ.get("PAPERLESS_TOKEN", "").strip()
    try:
        if not token or any(c.isspace() for c in token):
            raise InspectionError("set PAPERLESS_TOKEN to an existing authorised API token")
        raw = os.environ.get("PAPERLESS_URL", "")
        if urllib.parse.urlsplit(raw).username is not None:
            raise InspectionError("PAPERLESS_URL must not contain credentials")
        client = MetadataClient(upstream.check_url(raw, insecure=False), token)
        result = inspect_config(client)
        print(json.dumps(result, ensure_ascii=False, indent=2).replace(token, "[REDACTED]"))
        return 0
    except (InspectionError, upstream.ExportError, upstream.UsageError,
            ValueError, OSError, KeyError, TypeError) as error:
        message = str(error).replace(token, "[REDACTED]") if token else str(error)
        print("Inspection failed: " + message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Inspection interrupted; no archive changes were requested.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
