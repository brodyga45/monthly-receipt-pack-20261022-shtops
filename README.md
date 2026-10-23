# Monthly Receipt Pack

Turn a month of reviewed receipt metadata and local PDFs into one handoff ZIP:
a spreadsheet, a merged PDF for printing, and a manifest linking each row to its
pages and source hash. Documents stay in date/ID order, and source files remain
unchanged.

## Connect an existing Paperless archive

The [reusable connector](connector/README.md) reads a selected month of
already-reviewed monetary/text fields and original PDFs, then builds the same
CSV/combined-PDF/page-index handoff without preparing a JSON manifest manually.
It is for a technical operator with an authorised API token and an agreed
field/tag configuration. The [recorded output](connector/observed/real-paperless-3.3.3-october.zip)
uses fictional documents, not a customer archive.

The author ran this version against local Paperless-ngx3.3.3. Independent
automated review exercised repeat-month CLI workflows on a separate fictional
HTTP archive and checked the recorded output. See [verification and limits](connector/VERIFICATION.md).
PDF-only originals and monetary-total/text-category mapping are required;
recipient preference and supported customer setup remain separate questions.

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

The output must be new; existing output is preserved. Source PDFs must be
unencrypted and under the supplied source directory. Missing/invalid inputs stop
publication. Totals are decimal strings with at most two decimals; currencies
remain separate.

## Local packer scope

Inputs are a local JSON manifest and local PDFs. Amounts and categories are
already reviewed by the caller. OCR, financial extraction and a Paperless server
connection are outside this component. The caller also supplies the expected
document count: matching it checks the local selection, not the completeness of
an upstream query or archive. This tool packages data rather than certifying it.

The surrounding paid proposal plans to reuse
[Ildana-ai/paperless-export](https://github.com/Ildana-ai/paperless-export), whose
README and MIT licence were read. The original packer is independently written;
the new connector reuses that project's transport with its MIT licence retained. A
[recorded local Paperless 3.3.3 trial](compatibility/paperless-3.3.3/README.md)
retrieved reviewed API fields and original PDFs into the unchanged packer; its
recorded handoff was independently checked. The reusable generic connector is now
available above; provider setup and real-customer acceptance remain future paid scope.

## Supported integration

For help connecting this workflow to one existing Paperless-ngx installation,
[discuss a supported monthly handoff on Contra](https://contra.com/s/sFcPv6vo-paperless-monthly-receipt-handoff).
The service is listed at US$350, with a four-working-day delivery target after
agreement on the version, sample output, supported setup and payment terms.

The component can demonstrate a monthly handoff for users who already review
their metadata. A supported Paperless connection, field/date mapping and agreed
output can be scoped separately as paid development. There is no accepted paid
order, customer deployment or accounting guarantee. The local proof and generic connector received
independent automated product review; no customer installation has been accepted.

Developed with AI assistance. MIT licensed; dependencies retain their own rights.
