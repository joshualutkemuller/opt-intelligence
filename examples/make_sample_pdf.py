"""
Generate a sample optimization-brief PDF that the ingestion layer can parse.

    python examples/make_sample_pdf.py            # writes examples/sample_brief.pdf
    python examples/make_sample_pdf.py foo.pdf    # custom path

The document is written the way a treasury desk memo would be, so both the LLM
backend (Claude reads the PDF) and the offline heuristic backend can recover the
same optimization request from it.
"""

import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

BRIEF = [
    ("Money Market Portfolio Optimization Brief", "Title"),
    ("Prepared by: Treasury Liquidity Desk", "Normal"),
    ("Portfolio: PORT_204", "Normal"),
    ("", "Normal"),
    (
        "Objective. The desk seeks to <b>maximize net yield</b> across the "
        "eligible money market fund universe while preserving intraday "
        "liquidity and staying within our concentration policy.",
        "Normal",
    ),
    ("", "Normal"),
    ("Constraints.", "Heading2"),
    (
        "1. Daily liquidity must be at least 30% of assets under management.",
        "Normal",
    ),
    (
        "2. Weekly liquidity must be at least 50% of assets.",
        "Normal",
    ),
    (
        "3. Weighted average maturity (WAM) must remain below 60 days.",
        "Normal",
    ),
    (
        "4. Prime funds are limited to no more than 40% of the portfolio.",
        "Normal",
    ),
    (
        "5. No single fund may exceed 45% of total assets.",
        "Normal",
    ),
    ("", "Normal"),
    ("Scenario analysis.", "Heading2"),
    (
        "Please also evaluate a liquidity stress scenario in which daily and "
        "weekly liquidity requirements are raised, and a credit stress "
        "scenario reflecting a downgrade wave.",
        "Normal",
    ),
    ("", "Normal"),
    (
        "Deliverable. Provide a recommendation with the optimal allocation and "
        "the binding constraints.",
        "Normal",
    ),
]


def build(path: Path) -> None:
    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch)
    styles = getSampleStyleSheet()
    flow = []
    for text, style in BRIEF:
        if not text:
            flow.append(Spacer(1, 8))
        else:
            flow.append(Paragraph(text, styles[style]))
    doc.build(flow)
    print(f"wrote {path}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sample_brief.pdf"
    build(out)
