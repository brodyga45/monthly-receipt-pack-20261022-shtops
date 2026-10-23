# Verification of connector v1

The connector runtime SHA-256 is
`1a2f60e5c99d67859385bc71c8f610cc05aa09dad8362d311bf37b8147779939`.
The unchanged packer SHA-256 is
`290c45ae1df9b2765350383f3a85040873df1704740ffc58a1fb0bff1848a63a`.

Author evidence on23October2026: six HTTP integration tests passed, including
nine refusal modes in one parameterised case. A damaged-PDF exception found in
the first run was handled in the wrapper; the changed suite then passed.
The new connector entrypoint also ran against an isolated real Paperless-ngx
3.3.3 archive containing four fictional documents. Its October output has two
rows and three PDF pages; the PDF is byte-identical to the previously reviewed
and rendered example. The safe recorded ZIP and result are in `observed/`.
The real application run was author-observed, not independently rerun.

An independent automated product review verified the frozen17-file candidate
(40,828bytes; ZIP SHA-256
`01c1be48da480205c5ac0ce11255ea7fbc549b27b63a2f269b3c1b6b420885f8`).
It ran the actual CLI as a subprocess on a separately controlled fictional HTTP
archive, producing October and November packets with the same fields/tags and
no JSON input. It checked page references, hashes, negative amounts with separate
currencies, two-tag filtering, missing-value refusal before downloads, and
preservation of an existing output file. It separately read the supplied real
3.3.3 output. This review did not rerun the entire author suite, a VM, arbitrary
versions, spreadsheet import, physical printing or a full security audit.

The review kept the technical-operator workflow. The remaining purchase case is
an actual recipient wanting this merged-PDF/table format and a fitting reviewed
field configuration. No customer installation, financial correctness,
time-saving measurement, paid order or payment has been established.

Source files in this release match the reviewed runtime. Only release
README/verification prose is added or updated after that frozen review.

## Configuration ID discovery — 23 October 2026

`inspect_config.py` lists custom-field and tag IDs using an existing authorised
API token, so an operator need not find numerical IDs by hand before the first
handoff. Monetary/text types are candidates; field meaning, receipt selection
and reviewed values remain the operator's decisions. No customer or independent
player feedback is claimed for this change.

The author ran the previous six export integration tests plus four initial
metadata-discovery tests on fictional authenticated loopback HTTP archives:
10 passed. An independent scoped review found DISC-01: the reused transport
could follow a same-origin redirect to a document endpoint before refusing its
response. Discovery now uses its own redirect handler, which refuses every
HTTP redirect before requesting the destination. The unchanged exporter and
vendored source retain their previous behaviour.

After that correction, all five discovery integration tests passed (including
the new redirect regression); they cover multi-page fields/tags, unsupported
field types, empty collections, token redaction and seven other refusal modes.
The redirect regression checks the server received only the metadata request,
with no request to `/api/documents/`. This new helper has not been exercised
against a second live Paperless installation. These are synthetic HTTP checks,
not customer acceptance or evidence that a particular field is reviewed.

The independent reviewer repeated their separate normal/redirect CLI fixture on
the corrected helper. The normal listing remained correct; the same redirect
now exited before any document request. DISC-01 was closed within that tested
scope. No real customer archive or additional live Paperless deployment was
used for that retest.
