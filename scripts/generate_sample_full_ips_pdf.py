"""
Generate a full sample IPS PDF for the ingestion demo.

Run from the repository root:
    .venv/bin/python scripts/generate_sample_full_ips_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "examples/policies/sample_full_ips.pdf"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=LETTER,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Sample Full Investment Policy Statement",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "DemoTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0B171D"),
        spaceAfter=16,
    )
    heading = ParagraphStyle(
        "DemoHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#16252C"),
        spaceBefore=12,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "DemoBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.8,
        leading=13,
        textColor=colors.HexColor("#16252C"),
        spaceAfter=7,
    )

    story = [
        Paragraph("Sample Full Investment Policy Statement", title),
        Paragraph("1. Mandate Overview", heading),
        Paragraph(
            "Portfolio PORT_MVO_900 is a balanced institutional multi-asset portfolio "
            "with portfolio value of $250 million. The objective is to construct a "
            "diversified allocation that balances expected return, volatility, liquidity, "
            "and governance controls.",
            body,
        ),
        Paragraph(
            "The current review authorizes an optimization workflow to evaluate the "
            "portfolio against updated policy limits before any production action is "
            "taken.",
            body,
        ),
        PageBreak(),
        Paragraph("2. Return and Risk Policy", heading),
        Paragraph(
            "Target annual return should be 5.25%. Risk aversion lambda is 3.5 for "
            "the current review cycle. The optimizer should favor diversified return "
            "sources and penalize excess variance.",
            body,
        ),
        Paragraph(
            "The portfolio should remain long-only and should not introduce leveraged "
            "asset-class exposure during this recommendation review.",
            body,
        ),
        Paragraph("3. Allocation Constraints", heading),
        Paragraph(
            "Single asset class exposure must not exceed 40%. Cash floor must be at "
            "least 3% of portfolio value to preserve operating liquidity. The portfolio "
            "manager may not waive these constraints without governance approval.",
            body,
        ),
        _table(
            [
                ["Constraint", "Policy limit", "Workflow field"],
                ["Target annual return", "5.25%", "asset_allocation.target_return"],
                ["Risk aversion lambda", "3.5", "asset_allocation.risk_aversion"],
                ["Single asset class max", "40%", "asset_allocation.max_single_asset_weight"],
                ["Minimum cash weight", "3%", "asset_allocation.min_cash_weight"],
            ]
        ),
        PageBreak(),
        Paragraph("4. Current Portfolio Analytics", heading),
        Paragraph(
            "The current portfolio has expected return of 4.72%, volatility of 8.35%, "
            "Sharpe ratio of 0.31, cash allocation of 1.2%, and maximum single asset "
            "class exposure of 52%. These analytics should be shown before the "
            "optimization workflow applies the IPS constraints.",
            body,
        ),
        _table(
            [
                ["Asset class", "Current weight", "Policy comment"],
                ["US Equity", "52.0%", "Above single asset class maximum"],
                ["Core Bonds", "24.0%", "Within policy"],
                ["Alternatives", "15.0%", "Within policy"],
                ["Cash", "1.2%", "Below cash floor"],
            ]
        ),
        PageBreak(),
        Paragraph("5. Governance and Approval Policy", heading),
        Paragraph(
            "Materiality notional is $250 million. This review is a production "
            "constraint change because the approved concentration limit is being "
            "revised. Recommendation output must be reviewed before implementation.",
            body,
        ),
        Paragraph(
            "The evidence packet should include the source IPS, extracted fields, "
            "workflow context patch, before and after analytics, optimizer result, "
            "validation summary, and governance tier.",
            body,
        ),
        Spacer(1, 0.2 * inch),
        Paragraph("Prepared for Decision Intelligence demo use only.", body),
    ]
    document.build(story)
    print(f"Wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")


def _table(rows: list[list[str]]) -> Table:
    table = Table(rows, colWidths=[2.0 * inch, 1.5 * inch, 3.0 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16252C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.4),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#9CB2B4")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8F8")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


if __name__ == "__main__":
    main()
