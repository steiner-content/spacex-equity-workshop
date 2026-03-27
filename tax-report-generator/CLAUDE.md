# WNNW Wealth — Tax Report Generator

This tool takes a Hazel.ai tax analysis PDF and generates an on-brand WNNW Wealth PDF report.

## Setup

1. Make sure Python 3 is installed (`python3 --version`)
2. Install dependencies: `pip3 install -r requirements.txt`

## Usage

```bash
python3 generate_report.py "Tax Analysis - Client Name.pdf"
```

This will output a branded PDF in the same directory with `_WNNW.pdf` appended to the filename.

The script auto-detects `logo.png` in the same folder. To use a different logo:

```bash
python3 generate_report.py "Tax Analysis.pdf" --logo /path/to/logo.png
```

## What's in the folder

- `generate_report.py` — The main script. Extracts data from Hazel.ai PDFs and generates branded reports.
- `logo.png` — WNNW Wealth logo (wheat wreath mark + wordmark). Used on the cover page.
- `requirements.txt` — Python dependencies (pdfplumber, reportlab, Pillow).
- `CLAUDE.md` — This file.

## Notes

- Input must be a Hazel.ai tax analysis PDF. The parser is built around their specific format.
- The branded PDF includes: cover page, key figures, tax brackets, capital gains, interest/dividends, SE tax, QBI deduction, passive losses, deductions & credits, MAGI thresholds, observations & opportunities, balance due, and disclosures.
- Brand colors: Navy #21235F, Gold #F6D54E, Teal #6DCBD4.
