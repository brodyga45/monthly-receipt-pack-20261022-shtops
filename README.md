# Monthly Receipt Pack

A small runnable component for a proposed paid Paperless export integration.
Given reviewed metadata and local PDFs, it produces one ZIP containing a monthly
CSV, one PDF with those documents in date/ID order, and a manifest linking every
row to its PDF page range and source hash. It leaves source files unchanged.

This version reads a local JSON manifest. It has no Paperless server connection,
OCR, amount/category extraction, hosted UI or customer deployment. It does not
implement the complete proposed integration and is not a paid delivery. The
expected document count is supplied by the caller: reconciliation does not prove
that an upstream export/query was complete. No sales or customer acceptance exist.

## Try the included example

The sources are fictional. Two October documents become two spreadsheet rows and
three PDF pages; September/November documents are excluded. The supplied
[PDF](output/pdf/2026-10.pdf), [CSV](output/pdf/2026-10.csv) and
[ZIP](output/pdf/synthetic-october-pack.zip) show the result.

With Python 3.10 or later, create a virtual environment and install
`requirements.txt`. Then reproduce from the existing fixtures into a new file:

```sh
python receipt_pack.py fixtures/reviewed.json fixtures reproduced-pack.zip
```

The result reports `2026-10`, two documents and three pages. Open the ZIP to see
the sheet, PDF and manifest. Choose another output filename for a second run;
existing packages are deliberately preserved.

For development, install `requirements-dev.txt` and run `python -m unittest -v`.
The nine author checks and an independent positive workflow check passed on
macOS/Python 3.12.14. Windows/Linux and physical printing have not been tested.
`make_demo.py` is the original fixture generator: it should only be run in an
empty copy containing the source files, as the included example already exists.

For an existing reviewed manifest:

```sh
python receipt_pack.py reviewed.json ./pdfs ./monthly-pack.zip
```

The output must be new; existing output is never replaced. Source PDFs must be
unencrypted and under the supplied source directory. Missing/invalid inputs stop
publication. Totals are decimal strings, at most two decimals, and currencies are
separate columns; no mixed-currency total is manufactured. This is a packaging
tool, not a PDF security sanitizer or accounting validator. Do not feed untrusted
PDFs without the usual isolation for document processing.

The surrounding paid proposal plans to reuse
[Ildana-ai/paperless-export](https://github.com/Ildana-ai/paperless-export), whose
README and MIT licence were read. This proof contains independently written code;
it has not copied or integrated that project's source. Upstream adaptation,
supported-version checks and real-instance acceptance remain future paid scope.

## Supported integration

The component can demonstrate a monthly handoff for users who already review
their metadata. A supported Paperless connection, field/date mapping and agreed
output can be scoped separately as paid development. There is no accepted paid
order, customer deployment or accounting guarantee. The local proof received
independent product review; the full integration has not been built or accepted.

Developed with AI assistance. MIT licensed; dependencies retain their own rights.
