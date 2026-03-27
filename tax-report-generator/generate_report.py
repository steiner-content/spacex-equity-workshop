#!/usr/bin/env python3
"""
WNNW Wealth — On-Brand Tax Analysis Report Generator

Takes a Hazel.ai tax analysis PDF and produces a branded WNNW Wealth PDF
with proper colors, typography, logo, and professional layout.

Usage:
    python3 generate_report.py <input_pdf> [output_pdf] [--logo path/to/logo.png]
"""

import sys
import os
import re
import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# ── Brand Constants ──────────────────────────────────────────────────────────

NAVY       = HexColor("#21235F")
NAVY_DEEP  = HexColor("#181A4A")
GOLD       = HexColor("#F6D54E")
GOLD_SOFT  = HexColor("#edd587")
TEAL       = HexColor("#6DCBD4")
OFF_WHITE  = HexColor("#F8F8FB")
LIGHT_GRAY = HexColor("#EFEFEF")
TEXT_COLOR  = HexColor("#2D2D3E")
TEXT_LIGHT  = HexColor("#5A5A72")
WHITE       = white

PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch


# ── PDF Data Extraction ──────────────────────────────────────────────────────

def extract_tax_data(pdf_path):
    """Extract structured data from a Hazel.ai tax analysis PDF."""
    data = {
        "client_name": "",
        "filing_status": "",
        "tax_year": "",
        "state": "",
        "preparer": "",
        "draft_status": "",
        "balance_due_note": "",
        "key_figures": {},
        "tax_brackets": [],
        "bracket_room": "",
        "capital_gains_rates": [],
        "capital_gains_note": "",
        "interest_items": [],
        "dividend_items": [],
        "short_term_gains": [],
        "long_term_gains": [],
        "total_gains": "",
        "carryforward_st": "",
        "carryforward_lt": "",
        "se_tax": {},
        "qbi": {},
        "qbi_table": [],
        "qbi_limitation_note": "",
        "passive_losses": [],
        "passive_total": "",
        "passive_note": "",
        "deductions": [],
        "credits": [],
        "above_below_note": "",
        "magi_thresholds": [],
        "magi_value": "",
        "observations": [],
        "balance_due": {},
        "estimated_payments": [],
        "disclosures": "",
    }

    with pdfplumber.open(pdf_path) as pdf:
        all_text = []
        all_tables = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text.append(text)
            all_tables.append(page.extract_tables())

        full_text = "\n".join(all_text)

        # ── Page 1: Header & Key Figures ──
        p1 = all_text[0]

        m = re.search(r"Prepared for (.+?)$", p1, re.M)
        if m:
            data["client_name"] = m.group(1).strip()

        m = re.search(r"Filing Status:\s*(.+?)\s*·\s*Tax Year:\s*(\d{4})\s*·\s*State:\s*(.+?)\s*·\s*Prepared by:", p1)
        if m:
            data["filing_status"] = m.group(1).strip()
            data["tax_year"] = m.group(2).strip()
            data["state"] = m.group(3).strip()

        m = re.search(r"Prepared by:\s*\n?(.+?)$", p1, re.M)
        if m:
            data["preparer"] = m.group(1).strip()

        if "Draft Return" in p1:
            data["draft_status"] = "Draft Return – NOT YET FILED"

        m = re.search(r"(This analysis.*?April 15, \d{4}\.)", p1, re.S)
        if m:
            data["balance_due_note"] = m.group(1).replace("\n", " ").strip()

        # Key figures — parse the horizontal grid layout
        # Lines alternate: labels row, then values row
        # Line 8:  "Total Income Filing Status Qualified / Ordinary Dividends"
        # Line 9:  "$803,109 Married Filing $1,661 / $3,498"
        # Line 11: "Adjusted Gross Income Marginal Bracket ST / LT Capital Gains"
        # Line 12: "$745,078 35% $10,134 / $32,653"
        # etc.
        kf = data["key_figures"]
        lines = p1.split("\n")

        # Row 1: Total Income | Filing Status | Qualified/Ordinary Dividends
        m = re.search(r"\$([0-9,]+)\s+Married Filing\s+\$([0-9,]+)\s*/\s*\$([0-9,]+)", p1, re.S)
        if m:
            kf["total_income"] = "$" + m.group(1)
            kf["qualified_dividends"] = "$" + m.group(2)
            kf["ordinary_dividends"] = "$" + m.group(3)

        # Row 2: AGI | Marginal Bracket | ST/LT Capital Gains
        m = re.search(r"\$([0-9,]+)\s+(\d+%)\s+\$([0-9,]+)\s*/\s*\$([0-9,]+)", p1)
        if m:
            kf["agi"] = "$" + m.group(1)
            kf["marginal_bracket"] = m.group(2)
            kf["st_cap_gains"] = "$" + m.group(3)
            kf["lt_cap_gains"] = "$" + m.group(4)

        # Row 3: Deductions | Carryforward Loss | Taxable Income
        m = re.search(r"Deductions\s+Carryforward Loss\s+Taxable Income\s*\n\$([0-9,]+)\s+\$([0-9,]+)\s+\$([0-9,]+)", p1, re.S)
        if m:
            kf["deductions"] = "$" + m.group(1)
            kf["carryforward"] = "$" + m.group(2)
            kf["taxable_income"] = "$" + m.group(3)

        # Row 4: Effective Rate | Credits Claimed | Total Tax
        m = re.search(r"Effective Rate\s+Credits Claimed\s+Total Tax\s*\n([\d.]+%)\s+\$([0-9,]+)\s+\$([0-9,]+)", p1, re.S)
        if m:
            kf["effective_rate"] = m.group(1)
            kf["credits"] = "$" + m.group(2)
            kf["total_tax"] = "$" + m.group(3)

        # Row 5: Safe Harbor | Above The Line Deductions
        m = re.search(r"Safe Harbor\s+Above The Line Deductions\s*\n\$([0-9,]+)\s+\$([0-9,]+)", p1, re.S)
        if m:
            kf["safe_harbor"] = "$" + m.group(1)
            kf["above_line"] = "$" + m.group(2)

        # ── Page 2: Tax Brackets ──
        if len(all_tables) > 1:
            for tbl in all_tables[1]:
                if tbl and len(tbl) > 1 and tbl[0] and "Marginal Rate" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 4 and row[0] and "%" in str(row[0]):
                            data["tax_brackets"].append({
                                "rate": row[0],
                                "threshold": row[1],
                                "income": row[2],
                                "tax": row[3],
                            })

        m = re.search(r"Amount of ordinary income left in current tax bracket:\s*\$([0-9,]+)", full_text)
        if m:
            data["bracket_room"] = "$" + m.group(1)

        # ── Page 3: Capital Gains Rates ──
        if len(all_tables) > 2:
            for tbl in all_tables[2]:
                if tbl and len(tbl) > 1 and tbl[0] and "Rate" in str(tbl[0]) and "Qualified Income" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 5 and row[0] and "%" in str(row[0]):
                            data["capital_gains_rates"].append({
                                "rate": row[0],
                                "threshold": row[1],
                                "taxable_income": row[2],
                                "qualified_income": row[3],
                                "tax": row[4],
                            })

        m = re.search(r"Preferential rates on (\$[0-9,]+) of qualified income", full_text)
        if m:
            data["capital_gains_note"] = f"Preferential rates on {m.group(1)} of qualified income"

        # ── Page 4: Interest & Dividends ──
        # Table 1 (index 1) = Interest, Table 2 (index 2) = Dividends
        if len(all_tables) > 3:
            page4_tables = all_tables[3]
            # Interest table (second table on page, index 1)
            if len(page4_tables) > 1:
                tbl = page4_tables[1]
                if tbl and len(tbl) > 1:
                    for row in tbl[1:]:
                        if row and len(row) >= 2 and row[0] and row[1]:
                            if "Total" not in str(row[0]):
                                data["interest_items"].append({"desc": row[0], "amount": row[1]})
            # Dividend table (third table on page, index 2)
            if len(page4_tables) > 2:
                tbl = page4_tables[2]
                if tbl and len(tbl) > 1:
                    for row in tbl[1:]:
                        if row and len(row) >= 2 and row[0] and row[1]:
                            if "Total" not in str(row[0]):
                                data["dividend_items"].append({"desc": row[0], "amount": row[1]})

        # ── Page 5: Capital Gains Detail & SE Tax ──
        if len(all_tables) > 4:
            for tbl in all_tables[4]:
                if tbl and len(tbl) > 1 and tbl[0] and "Description" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 2 and row[0] and row[1]:
                            if not data["short_term_gains"]:
                                data["short_term_gains"].append({"desc": row[0], "amount": row[1]})
                            # Will be populated below

        # Parse short-term and long-term from text
        p5 = all_text[4] if len(all_text) > 4 else ""
        st_section = re.search(r"SHORT TERM.*?Total Short Term \$([0-9,]+)", p5, re.S)
        lt_section = re.search(r"LONG TERM.*?Total Long Term \$([0-9,]+)", p5, re.S)

        # Re-extract from tables properly
        if len(all_tables) > 4:
            data["short_term_gains"] = []
            data["long_term_gains"] = []
            for tbl in all_tables[4]:
                if tbl and len(tbl) > 1 and tbl[0] and "Description" in str(tbl[0]) and "Amount" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 2 and row[0] and row[1]:
                            # Check context from page text to determine ST vs LT
                            pass

        # Simpler: parse from text directly
        data["short_term_gains"] = []
        data["long_term_gains"] = []
        st_matches = re.findall(r"(?:SHORT TERM.*?)((?:(?!LONG TERM).)*?)Total Short Term", p5, re.S)
        lt_matches = re.findall(r"(?:LONG TERM.*?)((?:(?!TOTAL).)*?)Total Long Term", p5, re.S)

        # Just use the table data directly
        if len(all_tables) > 4 and len(all_tables[4]) >= 3:
            tbl_st = all_tables[4][1] if len(all_tables[4]) > 1 else []
            tbl_lt = all_tables[4][2] if len(all_tables[4]) > 2 else []
            if tbl_st and len(tbl_st) > 1:
                for row in tbl_st[1:]:
                    if row and len(row) >= 2 and row[0] and row[1]:
                        data["short_term_gains"].append({"desc": row[0], "amount": row[1]})
            if tbl_lt and len(tbl_lt) > 1:
                for row in tbl_lt[1:]:
                    if row and len(row) >= 2 and row[0] and row[1]:
                        data["long_term_gains"].append({"desc": row[0], "amount": row[1]})

        m = re.search(r"Total Gains/Losses:\s*(\$[0-9,]+)", p5)
        if m:
            data["total_gains"] = m.group(1)
        m = re.search(r"Short Term Loss\s*(\$[0-9,]+)", p5)
        if m:
            data["carryforward_st"] = m.group(1)
        m = re.search(r"Long Term Loss\s*(\$[0-9,]+)", p5)
        if m:
            data["carryforward_lt"] = m.group(1)

        # SE Tax
        se = data["se_tax"]
        m = re.search(r"Douglas – Net SE Income.*?Douglas – SE Tax.*?Douglas – Deductible Half\s*\n\$([0-9,]+)\s*\$([0-9,]+)\s*\$([0-9,]+)", p5)
        if m:
            se["doug_se_income"] = "$" + m.group(1)
            se["doug_se_tax"] = "$" + m.group(2)
            se["doug_deductible"] = "$" + m.group(3)
        m = re.search(r"Julie – Net SE Income.*?Julie – SE Tax.*?Julie – Deductible Half\s*\n\$([0-9,]+)\s*\$([0-9,]+)\s*\$([0-9,]+)", p5)
        if m:
            se["julie_se_income"] = "$" + m.group(1)
            se["julie_se_tax"] = "$" + m.group(2)
            se["julie_deductible"] = "$" + m.group(3)
        m = re.search(r"Combined SE Tax\s+Additional Medicare Tax\s+Total Employment Taxes\s*\n\$([0-9,]+)\s*\$([0-9,]+)\s*\$([0-9,]+)", p5)
        if m:
            se["combined_se"] = "$" + m.group(1)
            se["additional_medicare"] = "$" + m.group(2)
            se["total_employment"] = "$" + m.group(3)

        # ── Page 6: QBI Deduction ──
        p6 = all_text[5] if len(all_text) > 5 else ""
        m = re.search(r"Total deduction:\s*(\$[0-9,]+)", p6)
        if m:
            data["qbi"]["total"] = m.group(1)

        if len(all_tables) > 5:
            for tbl in all_tables[5]:
                if tbl and len(tbl) > 1 and tbl[0] and "Business" in str(tbl[0]) and "QBI" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 5 and row[0]:
                            data["qbi_table"].append({
                                "business": row[0],
                                "qbi": row[1],
                                "deduction": row[2],
                                "w2_wages": row[3],
                                "limitation": row[4],
                            })

        m = re.search(r"(QBI component.*?not income-limited\.)", p6, re.S)
        if m:
            data["qbi_limitation_note"] = m.group(1).replace("\n", " ").strip()

        # ── Page 7: Passive Losses ──
        if len(all_tables) > 6:
            for tbl in all_tables[6]:
                if tbl and len(tbl) > 1 and tbl[0] and "Activity" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 4 and row[0] and "Total" not in str(row[0]):
                            data["passive_losses"].append({
                                "activity": row[0],
                                "current_year": row[1],
                                "prior_suspended": row[2],
                                "total_suspended": row[3],
                            })
                        elif row and "Total" in str(row[0] or ""):
                            data["passive_total"] = row[3] if len(row) > 3 else ""

        p7 = all_text[6] if len(all_text) > 6 else ""
        m = re.search(r"(MAGI of.*?taxable transactions\.)", p7, re.S)
        if m:
            data["passive_note"] = m.group(1).replace("\n", " ").strip()

        # ── Page 8: Deductions & Credits ──
        if len(all_tables) > 7:
            for tbl in all_tables[7]:
                if tbl and len(tbl) > 0:
                    for row in tbl:
                        if row and len(row) >= 2 and row[0] and row[1]:
                            val = row[1].strip() if row[1] else ""
                            desc = row[0].strip() if row[0] else ""
                            if "Total" in desc:
                                continue
                            if any(kw in desc for kw in ["Standard", "QBI", "Self-Employment", "SEP", "Retirement"]):
                                data["deductions"].append({"desc": desc, "amount": val})
                            elif any(kw in desc for kw in ["Credit", "Foreign"]):
                                data["credits"].append({"desc": desc, "amount": val})

        p8 = all_text[7] if len(all_text) > 7 else ""
        m = re.search(r"(\$[0-9,]+ in above-the-line.*?to \$[0-9,]+\.)", p8, re.S)
        if m:
            data["above_below_note"] = m.group(1).replace("\n", " ").strip()

        # ── Page 9: MAGI Thresholds ──
        if len(all_tables) > 8:
            for tbl in all_tables[8]:
                if tbl and len(tbl) > 1 and tbl[0] and "MAGI Definition" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 2 and row[0]:
                            data["magi_thresholds"].append({
                                "definition": row[0],
                                "considerations": row[1] if len(row) > 1 else "",
                            })

        m = re.search(r"2025 MAGI:\s*(\$[0-9,]+)", full_text)
        if m:
            data["magi_value"] = m.group(1)

        # ── Page 10: Observations & Opportunities ──
        p10 = all_text[9] if len(all_text) > 9 else ""
        # Parse observation blocks line-by-line
        obs_lines = p10.split("\n")
        current_obs = None
        for line in obs_lines:
            # Check if this is a title line (ends with High/Medium/Low)
            title_match = re.match(r"^(.+?)\s+(High|Medium|Low)\s*$", line)
            if title_match:
                if current_obs:
                    data["observations"].append(current_obs)
                current_obs = {
                    "title": title_match.group(1).strip(),
                    "priority": title_match.group(2),
                    "body": "",
                    "savings": "",
                }
            elif current_obs:
                savings_match = re.match(r"Potential savings:\s*(.+)", line)
                if savings_match:
                    current_obs["savings"] = savings_match.group(1).strip()
                elif line.strip() and line.strip() not in ("Observations & Opportunities", "Key planning insights from the 2025 return"):
                    if current_obs["body"]:
                        current_obs["body"] += " "
                    current_obs["body"] += line.strip()
        if current_obs:
            data["observations"].append(current_obs)

        # ── Page 11: Balance Due & Estimated Payments ──
        p11 = all_text[10] if len(all_text) > 10 else ""
        m = re.search(r"Balance Due.*?Due Date.*?Estimated Total\s*\n\$([0-9,]+)\s+([\w\s,]+\d{4})\s+\$([0-9,]+)", p11)
        if m:
            data["balance_due"] = {
                "amount": "$" + m.group(1),
                "due_date": m.group(2).strip(),
                "estimated_total": "$" + m.group(3),
            }

        if len(all_tables) > 10:
            for tbl in all_tables[10]:
                if tbl and len(tbl) > 1 and tbl[0] and "Voucher" in str(tbl[0]):
                    for row in tbl[1:]:
                        if row and len(row) >= 3 and row[0]:
                            data["estimated_payments"].append({
                                "voucher": row[0],
                                "due_date": row[1],
                                "amount": row[2],
                            })

        # Disclosures
        m = re.search(r"Disclosures\s*\n(.*)", p11, re.S)
        if m:
            data["disclosures"] = m.group(1).strip()

    return data


# ── PDF Generation ───────────────────────────────────────────────────────────

def create_styles():
    """Create branded paragraph styles."""
    styles = {}

    styles["title"] = ParagraphStyle(
        "Title", fontName="Helvetica-Bold", fontSize=28,
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=6,
        leading=34
    )
    styles["subtitle"] = ParagraphStyle(
        "Subtitle", fontName="Helvetica", fontSize=13,
        textColor=TEXT_LIGHT, alignment=TA_CENTER, spaceAfter=4,
        leading=18
    )
    styles["section_label"] = ParagraphStyle(
        "SectionLabel", fontName="Helvetica-Bold", fontSize=9,
        textColor=TEAL, alignment=TA_LEFT, spaceAfter=4,
        spaceBefore=16, leading=12,
    )
    styles["section_title"] = ParagraphStyle(
        "SectionTitle", fontName="Helvetica-Bold", fontSize=18,
        textColor=NAVY, alignment=TA_LEFT, spaceAfter=8,
        leading=22
    )
    styles["body"] = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=10,
        textColor=TEXT_COLOR, alignment=TA_LEFT, spaceAfter=6,
        leading=14
    )
    styles["body_light"] = ParagraphStyle(
        "BodyLight", fontName="Helvetica", fontSize=9.5,
        textColor=TEXT_LIGHT, alignment=TA_LEFT, spaceAfter=4,
        leading=13
    )
    styles["callout"] = ParagraphStyle(
        "Callout", fontName="Helvetica-Bold", fontSize=11,
        textColor=NAVY, alignment=TA_LEFT, spaceAfter=6,
        leading=15
    )
    styles["kf_value"] = ParagraphStyle(
        "KFValue", fontName="Helvetica-Bold", fontSize=20,
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=2,
        leading=24
    )
    styles["kf_label"] = ParagraphStyle(
        "KFLabel", fontName="Helvetica", fontSize=8,
        textColor=TEXT_LIGHT, alignment=TA_CENTER, spaceAfter=0,
        leading=10
    )
    styles["obs_title"] = ParagraphStyle(
        "ObsTitle", fontName="Helvetica-Bold", fontSize=11,
        textColor=NAVY, alignment=TA_LEFT, spaceAfter=3,
        leading=14
    )
    styles["obs_body"] = ParagraphStyle(
        "ObsBody", fontName="Helvetica", fontSize=9.5,
        textColor=TEXT_COLOR, alignment=TA_LEFT, spaceAfter=2,
        leading=13
    )
    styles["obs_savings"] = ParagraphStyle(
        "ObsSavings", fontName="Helvetica-Oblique", fontSize=9,
        textColor=TEAL, alignment=TA_LEFT, spaceAfter=6,
        leading=12
    )
    styles["footer_text"] = ParagraphStyle(
        "FooterText", fontName="Helvetica", fontSize=7,
        textColor=TEXT_LIGHT, alignment=TA_CENTER,
        leading=9
    )
    styles["disclosure"] = ParagraphStyle(
        "Disclosure", fontName="Helvetica", fontSize=7.5,
        textColor=TEXT_LIGHT, alignment=TA_LEFT, spaceAfter=4,
        leading=10
    )
    styles["cover_client"] = ParagraphStyle(
        "CoverClient", fontName="Helvetica", fontSize=16,
        textColor=TEXT_COLOR, alignment=TA_CENTER, spaceAfter=4,
        leading=20
    )
    styles["cover_detail"] = ParagraphStyle(
        "CoverDetail", fontName="Helvetica", fontSize=11,
        textColor=TEXT_LIGHT, alignment=TA_CENTER, spaceAfter=2,
        leading=14
    )
    styles["priority_high"] = ParagraphStyle(
        "PriorityHigh", fontName="Helvetica-Bold", fontSize=8,
        textColor=WHITE, alignment=TA_CENTER,
    )
    styles["priority_med"] = ParagraphStyle(
        "PriorityMed", fontName="Helvetica-Bold", fontSize=8,
        textColor=NAVY, alignment=TA_CENTER,
    )

    return styles


class BrandedDocTemplate(SimpleDocTemplate):
    """Custom doc template with WNNW branding on every page."""

    def __init__(self, *args, logo_path=None, client_name="", tax_year="", **kwargs):
        self.logo_path = logo_path
        self.client_name = client_name
        self.tax_year = tax_year
        self.is_cover = True
        super().__init__(*args, **kwargs)

    def afterPage(self):
        self.is_cover = False

    def _draw_header_footer(self, canvas, doc):
        """Draw header and footer on content pages (not cover)."""
        canvas.saveState()

        # Header: thin navy bar with gold accent
        canvas.setFillColor(NAVY)
        canvas.rect(0, PAGE_H - 0.5 * inch, PAGE_W, 0.5 * inch, fill=1, stroke=0)

        # Gold accent line under header
        canvas.setFillColor(GOLD)
        canvas.rect(0, PAGE_H - 0.5 * inch - 2, PAGE_W, 2, fill=1, stroke=0)

        # Header text
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(MARGIN, PAGE_H - 0.34 * inch, "WNNW WEALTH")

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GOLD_SOFT)
        right_text = f"{self.tax_year} Tax Analysis — {self.client_name}"
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.34 * inch, right_text)

        # Footer
        canvas.setFillColor(LIGHT_GRAY)
        canvas.rect(0, 0, PAGE_W, 0.4 * inch, fill=1, stroke=0)

        canvas.setFillColor(TEXT_LIGHT)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, 0.16 * inch, "WNNW Wealth · WNNWWealth.com")
        canvas.drawRightString(
            PAGE_W - MARGIN, 0.16 * inch,
            f"Page {canvas.getPageNumber()}"
        )

        # Gold top border on footer
        canvas.setFillColor(GOLD)
        canvas.rect(0, 0.4 * inch, PAGE_W, 1.5, fill=1, stroke=0)

        canvas.restoreState()


def build_cover_page(data, styles, logo_path):
    """Build the cover page elements."""
    elements = []

    elements.append(Spacer(1, 1.5 * inch))

    # Logo — preserve aspect ratio
    if logo_path and os.path.exists(logo_path):
        from PIL import Image as PILImage
        pil_img = PILImage.open(logo_path)
        iw, ih = pil_img.size
        aspect = iw / ih
        logo_width = 2.8 * inch
        logo_height = logo_width / aspect
        img = Image(logo_path, width=logo_width, height=logo_height)
        img.hAlign = "CENTER"
        elements.append(img)
        elements.append(Spacer(1, 0.2 * inch))

    # Gold rule
    elements.append(HRFlowable(
        width="40%", thickness=2, color=GOLD,
        spaceAfter=16, spaceBefore=8, hAlign="CENTER"
    ))

    elements.append(Paragraph(
        f"{data['tax_year']} Federal Tax Analysis",
        styles["title"]
    ))

    elements.append(Spacer(1, 0.15 * inch))

    elements.append(Paragraph(
        f"Prepared for {data['client_name']}",
        styles["cover_client"]
    ))

    details = []
    if data["filing_status"]:
        details.append(data["filing_status"])
    if data["state"]:
        details.append(data["state"])
    if data["preparer"]:
        details.append(f"Prepared by: {data['preparer']}")

    if details:
        elements.append(Paragraph(
            " · ".join(details),
            styles["cover_detail"]
        ))

    if data["draft_status"]:
        elements.append(Spacer(1, 0.2 * inch))
        draft_style = ParagraphStyle(
            "Draft", fontName="Helvetica-Bold", fontSize=10,
            textColor=HexColor("#C0392B"), alignment=TA_CENTER,
            leading=14
        )
        elements.append(Paragraph(data["draft_status"], draft_style))

    if data["balance_due_note"]:
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(data["balance_due_note"], styles["body_light"]))
        styles["body_light"].alignment = TA_CENTER

    # Reset alignment
    styles["body_light"].alignment = TA_LEFT

    elements.append(Spacer(1, 0.6 * inch))

    # Gold rule at bottom
    elements.append(HRFlowable(
        width="60%", thickness=1, color=GOLD,
        spaceAfter=12, spaceBefore=0, hAlign="CENTER"
    ))

    wnnw_style = ParagraphStyle(
        "WNNWBottom", fontName="Helvetica", fontSize=9,
        textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=12
    )
    elements.append(Paragraph("WNNW Wealth · WNNWWealth.com", wnnw_style))

    elements.append(PageBreak())
    return elements


def make_section_header(label, title, styles):
    """Create a section header with teal label + navy title."""
    return [
        Paragraph(label.upper(), styles["section_label"]),
        Paragraph(title, styles["section_title"]),
    ]


def make_kf_card(value, label, styles):
    """Create a key-figure card as a mini table."""
    card = Table(
        [[Paragraph(value, styles["kf_value"])],
         [Paragraph(label, styles["kf_label"])]],
        colWidths=[2.1 * inch],
        rowHeights=[0.45 * inch, 0.3 * inch]
    )
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), OFF_WHITE),
        ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    return card


def make_branded_table(headers, rows, col_widths=None):
    """Create a branded data table with navy headers and alternating rows."""
    header_row = [Paragraph(f"<b>{h}</b>", ParagraphStyle(
        "TH", fontName="Helvetica-Bold", fontSize=8.5,
        textColor=WHITE, leading=11
    )) for h in headers]

    data_rows = []
    for row in rows:
        styled_row = []
        for cell in row:
            styled_row.append(Paragraph(str(cell), ParagraphStyle(
                "TD", fontName="Helvetica", fontSize=9,
                textColor=TEXT_COLOR, leading=12
            )))
        data_rows.append(styled_row)

    table_data = [header_row] + data_rows
    t = Table(table_data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, OFF_WHITE]),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def make_priority_badge(priority):
    """Create a colored priority badge."""
    if priority == "High":
        bg = HexColor("#C0392B")
        tc = WHITE
    elif priority == "Medium":
        bg = GOLD
        tc = NAVY
    else:
        bg = TEAL
        tc = WHITE

    t = Table(
        [[Paragraph(f"<b>{priority.upper()}</b>", ParagraphStyle(
            "Badge", fontName="Helvetica-Bold", fontSize=7,
            textColor=tc, alignment=TA_CENTER, leading=9
        ))]],
        colWidths=[0.6 * inch],
        rowHeights=[0.2 * inch]
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
    ]))
    return t


def build_report(data, styles, logo_path):
    """Build the full report as a list of Platypus flowables."""
    elements = []

    # ── Cover Page ──
    elements.extend(build_cover_page(data, styles, logo_path))

    kf = data["key_figures"]

    # ── Key Figures ──
    elements.extend(make_section_header("Summary", "Key Figures", styles))

    # Key figures grid (3 columns x 4 rows)
    kf_items = [
        (kf.get("total_income", "—"), "Total Income"),
        (kf.get("agi", "—"), "Adjusted Gross Income"),
        (kf.get("taxable_income", "—"), "Taxable Income"),
        (kf.get("total_tax", "—"), "Total Tax"),
        (kf.get("effective_rate", "—"), "Effective Rate"),
        (kf.get("marginal_bracket", "—"), "Marginal Bracket"),
        (kf.get("deductions", "—"), "Total Deductions"),
        (kf.get("credits", "—"), "Credits Claimed"),
        (kf.get("safe_harbor", "—"), "Safe Harbor (110%)"),
        (kf.get("st_cap_gains", "—"), "ST Capital Gains"),
        (kf.get("lt_cap_gains", "—"), "LT Capital Gains"),
        (kf.get("above_line", "—"), "Above-the-Line Deductions"),
    ]

    grid_rows = []
    for i in range(0, len(kf_items), 3):
        row = []
        for j in range(3):
            if i + j < len(kf_items):
                val, label = kf_items[i + j]
                row.append(make_kf_card(val, label, styles))
            else:
                row.append("")
        grid_rows.append(row)

    grid = Table(grid_rows, colWidths=[2.35 * inch] * 3, spaceBefore=8)
    grid.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(grid)
    elements.append(Spacer(1, 0.15 * inch))

    # ── Federal Tax Brackets ──
    elements.append(PageBreak())
    elements.extend(make_section_header("Tax Brackets", "Federal Ordinary Income Tax Brackets", styles))

    if data["bracket_room"]:
        elements.append(Paragraph(
            f"Marginal rate is {kf.get('marginal_bracket', '—')} with <b>{data['bracket_room']}</b> of room before the next bracket.",
            styles["body"]
        ))

    if data["tax_brackets"]:
        rows = [[b["rate"], b["threshold"], b["income"], b["tax"]] for b in data["tax_brackets"]]
        t = make_branded_table(
            ["Marginal Rate", "Threshold", "Income", "Tax"],
            rows,
            col_widths=[1.2 * inch, 2.0 * inch, 1.5 * inch, 1.5 * inch]
        )
        elements.append(t)
    elements.append(Spacer(1, 0.2 * inch))

    # ── Capital Gains & Qualified Dividends ──
    elements.extend(make_section_header("Capital Gains", "Capital Gains & Qualified Dividends", styles))

    if data["capital_gains_note"]:
        elements.append(Paragraph(data["capital_gains_note"], styles["body_light"]))

    if data["capital_gains_rates"]:
        rows = [[r["rate"], r["threshold"], r["taxable_income"], r["qualified_income"], r["tax"]]
                for r in data["capital_gains_rates"]]
        t = make_branded_table(
            ["Rate", "Threshold", "Taxable Income", "Qualified Income", "Tax"],
            rows,
            col_widths=[0.8 * inch, 1.6 * inch, 1.3 * inch, 1.3 * inch, 1.0 * inch]
        )
        elements.append(t)

    # ── Interest & Dividends ──
    elements.append(PageBreak())
    elements.extend(make_section_header("Schedule B", "Interest & Dividend Income", styles))

    if data["interest_items"] or data["dividend_items"]:
        # Side-by-side tables
        int_header = [Paragraph("<b>Interest Income</b>", ParagraphStyle(
            "IntH", fontName="Helvetica-Bold", fontSize=10,
            textColor=NAVY, leading=13
        ))]
        div_header = [Paragraph("<b>Dividend Income</b>", ParagraphStyle(
            "DivH", fontName="Helvetica-Bold", fontSize=10,
            textColor=NAVY, leading=13
        ))]

        int_rows = [[item["desc"], item["amount"]] for item in data["interest_items"]]
        div_rows = [[item["desc"], item["amount"]] for item in data["dividend_items"]]

        if int_rows:
            elements.append(Paragraph("<b>Interest Income</b>", styles["callout"]))
            elements.append(make_branded_table(["Description", "Amount"], int_rows,
                                               col_widths=[4.5 * inch, 1.5 * inch]))
            elements.append(Spacer(1, 0.15 * inch))

        if div_rows:
            elements.append(Paragraph("<b>Dividend Income</b>", styles["callout"]))
            elements.append(make_branded_table(["Description", "Amount"], div_rows,
                                               col_widths=[4.5 * inch, 1.5 * inch]))

    # ── Capital Gains & Losses Detail ──
    elements.append(Spacer(1, 0.2 * inch))
    elements.extend(make_section_header("Schedule D", "Capital Gains & Losses", styles))

    if data["short_term_gains"]:
        elements.append(Paragraph("<b>Short-Term Gains</b> (taxed at ordinary rates)", styles["body_light"]))
        rows = [[g["desc"], g["amount"]] for g in data["short_term_gains"]]
        elements.append(make_branded_table(["Description", "Amount"], rows,
                                           col_widths=[4.5 * inch, 1.5 * inch]))
        elements.append(Spacer(1, 0.1 * inch))

    if data["long_term_gains"]:
        elements.append(Paragraph("<b>Long-Term Gains</b> (preferential rates)", styles["body_light"]))
        rows = [[g["desc"], g["amount"]] for g in data["long_term_gains"]]
        elements.append(make_branded_table(["Description", "Amount"], rows,
                                           col_widths=[4.5 * inch, 1.5 * inch]))

    if data["total_gains"]:
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(
            f"Total Gains/Losses: <b>{data['total_gains']}</b> · "
            f"Carryforward: ST {data.get('carryforward_st', '$0')} / LT {data.get('carryforward_lt', '$0')}",
            styles["body"]
        ))

    # ── Self-Employment & Medicare Tax ──
    elements.append(PageBreak())
    elements.extend(make_section_header("Employment Tax", "Self-Employment & Medicare Tax", styles))

    se = data["se_tax"]
    if se:
        se_rows = []
        if "doug_se_income" in se:
            se_rows.append(["Douglas", se.get("doug_se_income", ""), se.get("doug_se_tax", ""), se.get("doug_deductible", "")])
        if "julie_se_income" in se:
            se_rows.append(["Julie", se.get("julie_se_income", ""), se.get("julie_se_tax", ""), se.get("julie_deductible", "")])

        if se_rows:
            elements.append(make_branded_table(
                ["Taxpayer", "Net SE Income", "SE Tax", "Deductible Half"],
                se_rows,
                col_widths=[1.2 * inch, 2.0 * inch, 1.5 * inch, 1.5 * inch]
            ))
            elements.append(Spacer(1, 0.1 * inch))

        if "total_employment" in se:
            summary_items = [
                (se.get("combined_se", "—"), "Combined SE Tax"),
                (se.get("additional_medicare", "—"), "Additional Medicare Tax"),
                (se.get("total_employment", "—"), "Total Employment Taxes"),
            ]
            row = [make_kf_card(v, l, styles) for v, l in summary_items]
            grid = Table([row], colWidths=[2.35 * inch] * 3, spaceBefore=8)
            grid.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(grid)

    # ── QBI Deduction ──
    elements.append(Spacer(1, 0.2 * inch))
    elements.extend(make_section_header("Section 199A", "QBI Deduction", styles))

    if data["qbi"].get("total"):
        elements.append(Paragraph(
            f"Total QBI Deduction: <b>{data['qbi']['total']}</b>",
            styles["callout"]
        ))

    if data["qbi_table"]:
        rows = [[q["business"], q["qbi"], q["deduction"], q["w2_wages"], q["limitation"]]
                for q in data["qbi_table"]]
        elements.append(make_branded_table(
            ["Business", "QBI", "Deduction", "W-2 Wages", "Limitation"],
            rows,
            col_widths=[1.6 * inch, 1.1 * inch, 1.0 * inch, 1.1 * inch, 1.2 * inch]
        ))

    if data["qbi_limitation_note"]:
        elements.append(Spacer(1, 0.08 * inch))
        elements.append(Paragraph(data["qbi_limitation_note"], styles["body_light"]))

    # ── Passive Activity Losses ──
    elements.append(PageBreak())
    elements.extend(make_section_header("Passive Activities", "Passive Activity Loss Analysis", styles))

    if data["passive_losses"]:
        rows = [[p["activity"], p["current_year"], p["prior_suspended"], p["total_suspended"]]
                for p in data["passive_losses"]]
        if data["passive_total"]:
            rows.append(["Total", "", "", data["passive_total"]])
        elements.append(make_branded_table(
            ["Activity", "Current Year", "Prior Suspended", "Total Suspended"],
            rows,
            col_widths=[2.2 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch]
        ))

    if data["passive_note"]:
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(Paragraph(data["passive_note"], styles["body_light"]))

    # ── Deductions & Credits ──
    elements.append(Spacer(1, 0.25 * inch))
    elements.extend(make_section_header("Deductions & Credits", "Summary of Deductions & Credits", styles))

    if data["deductions"]:
        rows = [[d["desc"], d["amount"]] for d in data["deductions"]]
        elements.append(Paragraph("<b>Deductions Claimed</b>", styles["callout"]))
        elements.append(make_branded_table(["Deduction", "Amount"], rows,
                                           col_widths=[4.5 * inch, 1.5 * inch]))
        elements.append(Spacer(1, 0.1 * inch))

    if data["credits"]:
        rows = [[c["desc"], c["amount"]] for c in data["credits"]]
        elements.append(Paragraph("<b>Credits Claimed</b>", styles["callout"]))
        elements.append(make_branded_table(["Credit", "Amount"], rows,
                                           col_widths=[4.5 * inch, 1.5 * inch]))

    if data["above_below_note"]:
        elements.append(Spacer(1, 0.08 * inch))
        elements.append(Paragraph(data["above_below_note"], styles["body_light"]))

    # ── MAGI Thresholds ──
    if data["magi_thresholds"]:
        elements.append(PageBreak())
        elements.extend(make_section_header("MAGI Analysis", "Proximity to Key Thresholds", styles))

        if data["magi_value"]:
            elements.append(Paragraph(
                f"2025 MAGI: <b>{data['magi_value']}</b>",
                styles["callout"]
            ))

        rows = [[m["definition"], m["considerations"]] for m in data["magi_thresholds"]]
        elements.append(make_branded_table(
            ["Threshold", "Planning Considerations"],
            rows,
            col_widths=[3.0 * inch, 3.5 * inch]
        ))

    # ── Observations & Opportunities ──
    if data["observations"]:
        elements.append(PageBreak())
        elements.extend(make_section_header("Planning", "Observations & Opportunities", styles))
        elements.append(Paragraph(
            f"Key planning insights from the {data['tax_year']} return",
            styles["body_light"]
        ))
        elements.append(Spacer(1, 0.1 * inch))

        for obs in data["observations"]:
            # Observation card with gold left border
            badge = make_priority_badge(obs["priority"])

            title_para = Paragraph(obs["title"], styles["obs_title"])
            body_para = Paragraph(obs["body"], styles["obs_body"])

            card_content = [[badge, title_para]]
            card_content.append(["", body_para])

            if obs["savings"]:
                savings_para = Paragraph(f"Potential savings: {obs['savings']}", styles["obs_savings"])
                card_content.append(["", savings_para])

            card = Table(card_content, colWidths=[0.7 * inch, 5.8 * inch])
            card.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, -1), OFF_WHITE),
                ("LINEBEFOREDECOR", (0, 0), (0, -1), 3, GOLD),
                ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
            ]))

            elements.append(KeepTogether([card, Spacer(1, 8)]))

    # ── Balance Due & Estimated Payments ──
    elements.append(PageBreak())
    elements.extend(make_section_header("Payments", "Balance Due & Estimated Payments", styles))

    bd = data["balance_due"]
    if bd:
        summary_items = [
            (bd.get("amount", "—"), "Balance Due"),
            (bd.get("due_date", "—"), "Due Date"),
            (bd.get("estimated_total", "—"), "2026 Estimated Total"),
        ]
        row = [make_kf_card(v, l, styles) for v, l in summary_items]
        grid = Table([row], colWidths=[2.35 * inch] * 3, spaceBefore=8)
        grid.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(grid)
        elements.append(Spacer(1, 0.15 * inch))

    if data["estimated_payments"]:
        rows = [[p["voucher"], p["due_date"], p["amount"]] for p in data["estimated_payments"]]
        elements.append(make_branded_table(
            ["Voucher", "Due Date", "Amount"],
            rows,
            col_widths=[1.5 * inch, 2.5 * inch, 2.0 * inch]
        ))

    # ── Disclosures ──
    if data["disclosures"]:
        elements.append(Spacer(1, 0.4 * inch))
        elements.append(HRFlowable(
            width="100%", thickness=0.5, color=LIGHT_GRAY,
            spaceAfter=8, spaceBefore=0
        ))
        elements.append(Paragraph("DISCLOSURES", styles["section_label"]))
        elements.append(Paragraph(data["disclosures"], styles["disclosure"]))

    return elements


def generate_pdf(input_pdf, output_pdf, logo_path=None):
    """Main entry point: extract data and generate branded PDF."""
    print(f"Reading tax analysis from: {input_pdf}")
    data = extract_tax_data(input_pdf)

    print(f"Generating branded report for: {data['client_name']}")

    doc = BrandedDocTemplate(
        output_pdf,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.6 * inch,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        logo_path=logo_path,
        client_name=data["client_name"],
        tax_year=data["tax_year"],
    )

    styles = create_styles()
    elements = build_report(data, styles, logo_path)

    def on_first_page(canvas, doc):
        """Cover page: no header/footer."""
        pass

    def on_later_pages(canvas, doc):
        """Content pages: branded header + footer."""
        doc._draw_header_footer(canvas, doc)

    doc.build(elements, onFirstPage=on_first_page, onLaterPages=on_later_pages)
    print(f"Report saved to: {output_pdf}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def find_logo():
    """Auto-detect logo in the same directory as this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for name in ["logo.png", "logo.jpg", "wnnw-logo.png", "2025_07_07_WW-Logo_RevisedSquare.png"]:
        path = os.path.join(script_dir, name)
        if os.path.exists(path):
            return path
    # Fall back to any PNG in the directory that looks like a logo
    for f in os.listdir(script_dir):
        if f.lower().endswith((".png", ".jpg")) and "logo" in f.lower():
            return os.path.join(script_dir, f)
    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate WNNW Wealth branded tax report")
    parser.add_argument("input_pdf", help="Path to Hazel.ai tax analysis PDF")
    parser.add_argument("output_pdf", nargs="?", default=None, help="Output PDF path (default: input name + _WNNW.pdf)")
    parser.add_argument("--logo", default=None, help="Path to WNNW logo image (PNG/JPG). Auto-detected if in same folder.")

    args = parser.parse_args()

    if args.output_pdf is None:
        base = os.path.splitext(args.input_pdf)[0]
        args.output_pdf = base + "_WNNW.pdf"

    logo = args.logo or find_logo()
    if logo:
        print(f"Using logo: {logo}")
    else:
        print("No logo found. Place logo.png in the same folder as this script, or use --logo.")

    generate_pdf(args.input_pdf, args.output_pdf, logo)
