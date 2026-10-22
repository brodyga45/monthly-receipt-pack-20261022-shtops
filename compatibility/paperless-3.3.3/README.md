# Paperless 3.3.3: one synthetic API-to-pack trial

On 22 October 2026 an author-run local Paperless-ngx 3.3.3 instance consumed four fictional PDFs. An authenticated October document-date query with page_size=1 returned two pages and the expected October 1/31 documents. Reviewed monetary/category fields and correspondents were read from the real API; original PDF downloads matched the uploaded fixtures byte for byte.

The unchanged receipt packer produced two CSV rows (12.30/7.07 EUR), page ranges 1–2/3–3 and three PDF pages. The output PDF is byte-identical to the earlier independently reviewed sample. A separate artifact review checked recorded inputs, CSV, manifest and source hashes; it did not independently observe the live API, VM or container image. The isolated lab was stopped after the run.

[Download the frozen recording](trial-recording.zip), SHA-256 `467947123b44807f715f4a0118aa56644debaa6b1d39961bad107bd80dee5c60` (20,859 bytes). It includes the exact one-off driver, an output verifier, unchanged packer snapshot, fictional fixtures and recorded handoff. It excludes credentials, environment files, the VM and Paperless server code. After extraction, with the included requirements installed, `python verify_result.py --lab observed` checks the recording without a server.

This reduces one compatibility uncertainty. It is not a supported connector or an existing hosted-provider deployment. It does not perform OCR/financial extraction, validate arbitrary versions or archives, establish an end-user workflow, or prove printer/accountant/customer acceptance. Metadata was deliberately supplied as reviewed test input. No paid order or payment is claimed.

Official upstream: [release 3.3.3](https://github.com/paperless-ngx/paperless-ngx/releases/tag/v3.3.3), [SQLite container example](https://raw.githubusercontent.com/paperless-ngx/paperless-ngx/v3.3.3/docker/compose/docker-compose.sqlite.yml). Application image used: `ghcr.io/paperless-ngx/paperless-ngx@sha256:dba0242c1df1843643df4eb50ce5639f3a7900f414879088fd5bed8eaf2d456d` (ARM64 Linux).
