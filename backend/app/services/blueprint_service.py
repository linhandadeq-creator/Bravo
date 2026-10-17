"""mRNA construct blueprint (research schematic).

Renders a construct into a labelled blueprint: ordered segments, a simulated
nucleic-acid sequence and a lightweight SVG schematic. This is a research
schematic derived from simulated data — not a validated therapeutic design and
not for clinical or human use.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.blueprint.formats import FORMAT_CIRCRNA, FORMAT_SARNA
from app.models.construct import SimulationConstruct
from app.models.neoantigen import NeoantigenCandidate

DISCLAIMER = (
    "Research schematic generated from simulated data. It does not represent "
    "clinical or therapeutic efficacy and must not be used for clinical "
    "decision-making, manufacturing, or human use."
)

_SEGMENT_WIDTHS = {
    "5PRIME": 96,
    "3PRIME": 120,
    "ANTIGEN": 150,
    "SPACER": 74,
    "PIE_EXON": 84,
    "IRES": 130,
    "REPLICASE": 170,
    "SUBGENOMIC_PROMOTER": 70,
}
_SEGMENT_TYPES = {
    "5PRIME": "5' cap / UTR",
    "3PRIME": "3' UTR / poly(A)",
    "ANTIGEN": "Antigen",
    "SPACER": "Linker",
    "PIE_EXON": "PIE exon",
    "IRES": "IRES (simulated)",
    "REPLICASE": "Replicase (simulated)",
    "SUBGENOMIC_PROMOTER": "Subgenomic promoter",
}


def _edge_segments(fmt: str, start_index: int) -> tuple[list[dict], list[dict]]:
    """Format-specific fixed segments placed around the antigen cassette."""
    def make(index: int, seg_type: str, label: str) -> dict:
        return {
            "index": index,
            "type": seg_type,
            "label": label,
            "title": _SEGMENT_TYPES[seg_type],
        }

    if fmt == FORMAT_CIRCRNA:
        pre = [
            make(start_index, "PIE_EXON", "[PIE_3P]"),
            make(start_index + 1, "IRES", "[IRES]"),
        ]
        post = [make(0, "PIE_EXON", "[PIE_5P]")]
    elif fmt == FORMAT_SARNA:
        pre = [
            make(start_index, "5PRIME", "[5PRIME]"),
            make(start_index + 1, "REPLICASE", "[REPLICASE]"),
            make(start_index + 2, "SUBGENOMIC_PROMOTER", "[SGP]"),
        ]
        post = [make(0, "3PRIME", "[3PRIME]")]
    else:
        pre = [make(start_index, "5PRIME", "[5PRIME]")]
        post = [make(0, "3PRIME", "[3PRIME]")]
    return pre, post


def build_blueprint(db: Session, construct: SimulationConstruct) -> dict:
    candidate_ids = [item.candidate_id for item in (construct.items or [])]
    candidates = {}
    if candidate_ids:
        from sqlalchemy import select

        rows = (
            db.execute(
                select(NeoantigenCandidate).where(
                    NeoantigenCandidate.id.in_(candidate_ids)
                )
            )
            .scalars()
            .all()
        )
        candidates = {row.id: row for row in rows}

    fmt = construct.simulation_format
    pre, post = _edge_segments(fmt, 0)
    segments: list[dict] = list(pre)
    for item in construct.items or []:
        candidate = candidates.get(item.candidate_id or "")
        segments.append(
            {
                "index": len(segments),
                "type": "ANTIGEN",
                "label": f"[{item.label}]",
                "title": _SEGMENT_TYPES["ANTIGEN"],
                "candidate_id": item.candidate_id,
                "gene": candidate.gene if candidate else None,
                "protein_change": candidate.protein_change if candidate else None,
                "hla_allele": candidate.hla_allele if candidate else None,
                "peptide_sequence": candidate.peptide_sequence if candidate else None,
                "peptide_representation": candidate.peptide_representation
                if candidate
                else None,
            }
        )
        if item.spacer:
            segments.append(
                {
                    "index": len(segments),
                    "type": "SPACER",
                    "label": "[SPACER]",
                    "title": _SEGMENT_TYPES["SPACER"],
                }
            )
    segments.append(
        {
            "index": len(segments),
            "type": post[0]["type"],
            "label": post[0]["label"],
            "title": post[0]["title"],
        }
    )

    return {
        "construct_id": construct.id,
        "analysis_run_id": construct.analysis_run_id,
        "name": construct.name,
        "simulation_format": construct.simulation_format,
        "status": construct.status,
        "construct_representation": construct.construct_representation,
        "circular": fmt == FORMAT_CIRCRNA,
        "ligation_junction": "Position 0 (5' end ligated to 3' end)" if fmt == FORMAT_CIRCRNA else None,
        "sequence": construct.sequence,
        "sequence_length": len(construct.sequence or ""),
        "candidate_count": len(candidate_ids),
        "segments": segments,
        "production_package": construct.simulation_output,
        "sequence_qc": (construct.qc_summary or {}).get("sequence_qc"),
        "production_ready": bool(
            (construct.simulation_output or {}).get("production_ready")
        ),
        "severity": construct.status,
        "disclaimer": DISCLAIMER,
    }


def blueprint_svg(segments: list[dict]) -> str:
    height = 120
    margin = 20
    gap = 14
    widths = [_SEGMENT_WIDTHS.get(seg["type"], 120) for seg in segments]
    total = margin * 2 + sum(widths) + gap * max(0, len(segments) - 1)

    parts: list[str] = []
    x = margin
    for seg, width in zip(segments, widths):
        fill = "#ffffff"
        stroke = "#c9ccd1"
        if seg["type"] == "ANTIGEN":
            fill = "#eef2f7"
            stroke = "#9aa3ad"
        elif seg["type"] == "SPACER":
            fill = "#f7f8fa"
        elif seg["type"] == "PIE_EXON":
            fill = "#f1f6f3"
        elif seg["type"] == "IRES":
            fill = "#f3f2f9"
        elif seg["type"] == "REPLICASE":
            fill = "#f6f3ee"
        elif seg["type"] == "SUBGENOMIC_PROMOTER":
            fill = "#f4f5f7"
        parts.append(
            f'<rect x="{x}" y="54" width="{width}" height="34" rx="5" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        )
        cx = x + width / 2
        parts.append(
            f'<text x="{cx}" y="76" text-anchor="middle" font-size="12" '
            f'font-family="-apple-system,Segoe UI,PingFang SC,sans-serif" fill="#1a1a1a">{seg["label"]}</text>'
        )
        subtitle = seg.get("gene") or seg.get("title") or ""
        if seg["type"] == "ANTIGEN" and seg.get("protein_change"):
            subtitle = f'{seg.get("gene") or ""} {seg["protein_change"]}'.strip()
        if subtitle:
            parts.append(
                f'<text x="{cx}" y="42" text-anchor="middle" font-size="10" '
                f'font-family="-apple-system,Segoe UI,PingFang SC,sans-serif" fill="#6b7280">{subtitle}</text>'
            )
        if seg["type"] == "ANTIGEN" and seg.get("hla_allele"):
            parts.append(
                f'<text x="{cx}" y="104" text-anchor="middle" font-size="9" '
                f'font-family="-apple-system,Segoe UI,PingFang SC,sans-serif" fill="#6b7280">{seg["hla_allele"]}</text>'
            )
        x += width + gap

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {int(total)} {height}" '
        f'width="{int(total)}" height="{height}" role="img" '
        f'aria-label="mRNA construct blueprint">'
        f'<rect x="0" y="0" width="{int(total)}" height="{height}" fill="#ffffff"/>'
        + "".join(parts)
        + "</svg>"
    )


def blueprint_pdf(blueprint: dict) -> bytes:
    """Render the blueprint to a PDF (Chinese-capable schematic + tables)."""
    import io

    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    font = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(font))

    def esc(value) -> str:
        text = "" if value is None else str(value)
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    body = ParagraphStyle("body", fontName=font, fontSize=9, leading=13)
    note = ParagraphStyle("note", fontName=font, fontSize=8.5, leading=12, textColor=colors.HexColor("#6b7280"))
    h1 = ParagraphStyle("h1", fontName=font, fontSize=16, leading=21, spaceAfter=4)
    h2 = ParagraphStyle("h2", fontName=font, fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=5)
    cell = ParagraphStyle("cell", fontName=font, fontSize=8, leading=10)

    segments = blueprint["segments"]
    widths = [_SEGMENT_WIDTHS.get(seg["type"], 120) for seg in segments]
    gap = 12
    total = sum(widths) + gap * max(0, len(segments) - 1)
    scale = min(1.0, 470 / total) if total else 1.0

    drawing = Drawing(total * scale, 90)
    x = 0.0
    for seg, width in zip(segments, widths):
        w = width * scale
        fill = colors.white
        stroke = colors.HexColor("#c9ccd1")
        if seg["type"] == "ANTIGEN":
            fill = colors.HexColor("#eef2f7")
            stroke = colors.HexColor("#9aa3ad")
        elif seg["type"] == "SPACER":
            fill = colors.HexColor("#f7f8fa")
        drawing.add(Rect(x, 28, w, 28, rx=4, ry=4, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))
        drawing.add(String(x + w / 2, 40, seg["label"], fontName=font, fontSize=8, textAnchor="middle"))
        subtitle = None
        if seg["type"] == "ANTIGEN":
            subtitle = f'{seg.get("gene") or ""} {seg.get("protein_change") or ""}'.strip()
            if seg.get("hla_allele"):
                drawing.add(String(x + w / 2, 19, seg["hla_allele"], fontName=font, fontSize=6.5, fillColor=colors.HexColor("#6b7280"), textAnchor="middle"))
        if subtitle:
            drawing.add(String(x + w / 2, 61, subtitle, fontName=font, fontSize=6.5, fillColor=colors.HexColor("#6b7280"), textAnchor="middle"))
        x += w + gap

    grid = [[Paragraph(h, cell) for h in ["Segment", "Type", "Gene", "Protein change", "HLA", "Peptide"]]]
    for seg in segments:
        grid.append(
            [
                Paragraph(esc(seg["label"]), cell),
                Paragraph(esc(seg.get("title") or ""), cell),
                Paragraph(esc(seg.get("gene")), cell),
                Paragraph(esc(seg.get("protein_change")), cell),
                Paragraph(esc(seg.get("hla_allele")), cell),
                Paragraph(esc(seg.get("peptide_sequence")), cell),
            ]
        )
    seg_table = Table(grid, repeatRows=1)
    seg_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f7f8fa")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    story = [
        Paragraph("mRNA vaccine blueprint", h1),
        Paragraph(esc(blueprint["disclaimer"]), note),
        Paragraph(
            f"Construct ID: {esc(blueprint['construct_id'])} · Status: {esc(blueprint['status'])} · "
            f"Format：{esc(blueprint['simulation_format'])} · Antigens: {blueprint['candidate_count']}",
            note,
        ),
        Paragraph("Construct schematic", h2),
        drawing,
        Paragraph("Antigen sequence (ordered)", h2),
        seg_table,
        Paragraph(f"Simulated nucleotide sequence ({blueprint['sequence_length']} nt）", h2),
        Paragraph(esc(blueprint["sequence"] or "—"), ParagraphStyle("seq", fontName="Courier", fontSize=7, leading=9)),
        Spacer(1, 6),
        Paragraph(esc(blueprint["disclaimer"]), note),
    ]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title="mRNA vaccine blueprint",
    )
    doc.build(story)
    return buffer.getvalue()


def build_blueprint_html(blueprint: dict) -> str:
    svg = blueprint_svg(blueprint["segments"])
    rows = "".join(
        "<tr>"
        f"<td>{seg['label']}</td>"
        f"<td>{seg.get('title', '')}</td>"
        f"<td>{seg.get('gene') or '—'}</td>"
        f"<td>{seg.get('protein_change') or '—'}</td>"
        f"<td>{seg.get('hla_allele') or '—'}</td>"
        f"<td>{seg.get('peptide_sequence') or '—'}</td>"
        "</tr>"
        for seg in blueprint["segments"]
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>mRNA vaccine blueprint (research simulation)</title>
<style>
body {{ margin:0; padding:40px 24px; background:#fff; color:#1a1a1a;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",Arial,sans-serif; }}
.sheet {{ max-width:940px; margin:0 auto; }}
h1 {{ font-size:20px; font-weight:600; margin:0 0 6px; }}
h2 {{ font-size:14px; font-weight:600; margin:28px 0 10px; padding-bottom:6px; border-bottom:1px solid #e5e7eb; }}
p.d {{ color:#6b7280; font-size:12px; border-left:2px solid #111827; padding-left:12px; }}
.paper {{ border:1px solid #e5e7eb; border-radius:6px; padding:18px; overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th {{ text-align:left; color:#6b7280; font-weight:500; font-size:11px; padding:7px 10px; border-bottom:1px solid #e5e7eb; }}
td {{ padding:8px 10px; border-bottom:1px solid #f1f2f4; }}
.seq {{ font-family:ui-monospace,Menlo,monospace; font-size:11px; word-break:break-all;
  border:1px solid #e5e7eb; border-radius:6px; padding:12px; color:#374151; }}
</style></head><body><div class="sheet">
<h1>mRNA vaccine blueprint</h1>
<p class="d">{blueprint['disclaimer']}</p>
<p class="d">Construct ID: {blueprint['construct_id']} · Status: {blueprint['status']} · Format: {blueprint['simulation_format']} · Antigens: {blueprint['candidate_count']}</p>
<h2>Construct schematic</h2>
<div class="paper">{svg}</div>
<h2>Antigen sequence (ordered)</h2>
<table><thead><tr><th>Segment</th><th>Type</th><th>Gene</th><th>Protein change</th><th>HLA</th><th>Peptide</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Simulated nucleotide sequence ({blueprint['sequence_length']} nt）</h2>
<div class="seq">{blueprint['sequence'] or '—'}</div>
</div></body></html>"""
