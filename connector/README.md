# Monthly Receipt Handoff — reusable connector

Create one accountant handoff ZIP from a month of **already-reviewed** Paperless
metadata and original PDF documents. The ZIP contains a CSV, one combined PDF,
a row-to-page/source-hash manifest and a selection receipt. No JSON manifest
needs to be prepared manually.

This is a local command-line component for a technical operator. It does not
extract or check financial facts, change the archive, submit accounting records,
book a service or send the result to another person. A supported installation
for a customer's version, fields and infrastructure remains separately agreed
work. There is no accepted customer order or payment.

## Run it

Python 3.10+ and the pinned dependency in `requirements.txt` are required. In a
virtual environment, install that file with `python -m pip install -r requirements.txt`.
Use an **existing authorised** Paperless API token. Keep the token in the process
environment rather than command arguments, source files or a public support post.
For example, have your normal local environment set `PAPERLESS_URL` and
`PAPERLESS_TOKEN`, then run:

```sh
python monthly_handoff.py 2026-10 october-handoff.zip \
  --total-field 7 --category-field 8 --tag-id 5
```

Replace the example field/tag IDs with your own configuration. The total field
must be **monetary**, with values such as `EUR12.30`. The category field must be
**text**, with reviewed labels such as `Supplies`. The correspondent supplies
the vendor name. This candidate does not map select-category, numerical-only
amount or OCR-text fields. It never fills missing facts with zero or guesses.

`--tag-id` is repeatable: a document must have every specified tag. Without it,
the selection is all accessible documents whose **document-created date** is
in the chosen month. It is not the upload month or an automatic definition of
which documents belong in your accounts. Confirm your receipt filter and date
meaning before relying on the handoff. Non-PDF originals stop the run rather
than being silently omitted or replaced with an unverified conversion.

The command prints the month, selected count, PDF page count and output path.
For an empty selection it reports zero documents and `output: null`, without
writing an empty ZIP. An existing output path is preserved; choose a new name
for a new run.

Read the CSV and its page references, then open the combined PDF before handing
it on. CSV contains decimal text without floating-point calculation. Your
spreadsheet application can still round very large numbers when opening CSV;
these tests do not establish Excel/Numbers import behaviour.

## What is checked

The connector retrieves every page, reconciles the API count and unique IDs,
checks dates/tags and required fields, and downloads original PDFs. After the
downloads it retrieves the selection again and compares document metadata,
field types and correspondent names. Observed changes stop publication.
Matching reads are **not an atomic server snapshot** and do not certify that
your archive or accounting selection is complete. Use a quiet archive for the run.

Temporary downloads use a private temporary directory beside the output and
are removed on success or failure. The final ZIP appears atomically after
validation; interrupted/failed runs do not replace an existing output. Inspect
the output filename before retrying an interrupted final step.

Default limits are 500 documents, 25 MB per PDF and 250 MB downloaded in total.
`--max-documents`, `--max-pdf-bytes` and `--max-total-bytes` let the operator
choose positive limits for the machine. The run fails if a limit is exceeded;
it never silently truncates the package. PDF parsing/merging uses memory.

HTTPS certificates are verified. Plain HTTP is limited by the reused transport
to a private/local host; there is no insecure-public-HTTP or certificate-bypass
flag here. Redirects and pagination cannot leave the named instance. This code
changes no CORS, network, account or server configuration. Output contains no
token or instance hostname.

## Reuse and evidence

`vendor/paperless_export.py` is the unchanged MIT-licensed transport/source from
[Ildana-ai/paperless-export](https://github.com/Ildana-ai/paperless-export),
version 0.4.0, Git blob `68b416667b89280fe57cdc03ecbeae49fb264fb0`, SHA-256
`64ccc4c84ed6f68238aa9e8b85571fb192c5ec68aaae2ca41e629414e5c69dfa`.
Its licence is retained in `vendor/LICENSE-paperless-export.txt`. The connector
uses its URL checks, authenticated JSON transport, same-origin redirect handling
and pagination-origin checks. It reads raw monetary strings, preserving exact
decimal values rather than routing them through a floating-point renderer.
This is not a claim that existing export capabilities are absent upstream.

`receipt_pack.py` and fictional PDFs are the existing independently reviewed
Monthly Receipt Pack component. On 23 October 2026 the author ran this new
connector's entrypoint against the retained isolated Paperless-ngx 3.3.3 fixture
archive. It selected the two October originals from four adjacent-month
documents and produced the expected two rows/three PDF pages. The merged PDF
was byte-identical to the previously independently rendered sample. The safe
record and ZIP are in `observed/`. This is one author-observed local application
run. An independent automated review then exercised repeat October/November
CLI workflows on a separate fictional HTTP archive and checked the supplied
real-run artifact. See [verification](VERIFICATION.md). No provider
deployment, customer acceptance or arbitrary-version compatibility is claimed.

Six HTTP integration tests pass, including nine failure modes in one parameterised
case. The first author test run exposed an uncaught damaged-PDF exception; the
connector now reports that error cleanly, and the changed integration suite
passed after the correction. This does not repeat or extend the earlier
independent review to unobserved customer documents.

Run the connector's meaningful integration checks with:

```sh
python -m unittest -v test_handoff
```

They use a fictional loopback HTTP archive and actual authenticated HTTP GETs,
PDF parsing and ZIP readback. They do not contact an external archive or need
customer credentials. Authored with AI assistance; own code is MIT-licensed.
