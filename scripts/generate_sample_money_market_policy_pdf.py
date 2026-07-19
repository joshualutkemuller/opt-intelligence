#!/usr/bin/env python3
"""Generate the sample money-market policy PDF used in the UI video demo."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT = Path("examples/policies/sample_money_market_policy.pdf")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=14,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0f766e"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8,
    )

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Money Market Portfolio Review - Treasury Mandate",
    )

    story = [
        Paragraph("Money Market Portfolio Review - Treasury Mandate", title),
        Paragraph("Portfolio Scope", heading),
        Paragraph(
            "Mandate: Optimize the treasury liquidity sleeve for Portfolio "
            "PORT_MMF_901. Current portfolio: Total investable cash balance is "
            "$625 million. The current allocation is overweight a small number "
            "of government and prime money-market funds and should be reviewed "
            "against liquidity and concentration controls.",
            body,
        ),
        Paragraph("Investment Requirements", heading),
        _requirements_table(),
        Spacer(1, 8),
        Paragraph(
            "Optimization goal: maximize net 7-day annualized yield while "
            "satisfying liquidity, WAM, prime exposure, and concentration "
            "requirements. Use recommendation mode only.",
            body,
        ),
        Paragraph("Governance Notes", heading),
        Paragraph(
            "Governance: Materiality notional is $625 million. Estimated PnL "
            "impact is $0. This is not a production constraint change.",
            body,
        ),
        Paragraph("Current Portfolio Observations", heading),
        Paragraph(
            "The desk wants a clean before/after review showing baseline yield, "
            "optimized yield, daily and weekly liquidity, WAM, prime exposure, "
            "single-fund concentration, binding constraints, and an audit-ready "
            "mapping from this PDF into optimizer inputs.",
            body,
        ),
    ]

    doc.build(story)
    print(OUTPUT)


def _requirements_table() -> Table:
    rows = [
        ["Control", "Policy language", "Optimizer field"],
        ["Daily liquidity", "Daily liquidity must be at least 32%.", "daily_liquidity_req"],
        ["Weekly liquidity", "Weekly liquidity minimum 68%.", "weekly_liquidity_req"],
        ["Prime funds", "Prime fund exposure must not exceed 35%.", "max_prime_fraction"],
        ["WAM", "Weighted average maturity must stay under 50 days.", "max_wam_days"],
        ["Concentration", "Single-fund exposure must not exceed 40%.", "max_single_fund"],
    ]
    table = Table(rows, colWidths=[1.35 * inch, 3.05 * inch, 1.75 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334155")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


if __name__ == "__main__":
    main()
