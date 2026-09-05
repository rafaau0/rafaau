from __future__ import annotations

import calendar
import html
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .database import Client, Post
from .paths import EXPORTS_DIR


MONTH_NAMES = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]
STATUS_COLORS = {
    "Pendente": colors.HexColor("#F59E0B"),
    "Em andamento": colors.HexColor("#3B82F6"),
    "Concluído": colors.HexColor("#10B981"),
}


class PDFGenerator:
    """Cria um calendário editorial em PDF."""

    def __init__(self, output_dir: Path = EXPORTS_DIR) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self.styles.add(
            ParagraphStyle(
                name="TitleWhite",
                parent=self.styles["Title"],
                textColor=colors.white,
                fontSize=18,
                leading=21,
                spaceAfter=0,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CoverInfo",
                parent=self.styles["BodyText"],
                textColor=colors.HexColor("#111827"),
                fontSize=8,
                leading=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SmallMuted",
                parent=self.styles["BodyText"],
                textColor=colors.HexColor("#64748B"),
                fontSize=8,
                leading=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="CellText",
                parent=self.styles["BodyText"],
                fontSize=6.4,
                leading=7.3,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="WeekdayHeader",
                parent=self.styles["BodyText"],
                alignment=TA_CENTER,
                textColor=colors.white,
                fontSize=7.5,
                leading=8.5,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Centered",
                parent=self.styles["BodyText"],
                alignment=TA_CENTER,
                fontSize=9,
                leading=11,
            )
        )

    def export_month(self, client: Client, posts: list[Post], year: int, month: int) -> Path:
        identity = client.id if client.id is not None else "sem_id"
        filename = f"calendario_{self._slug(client.name)}_{identity}_{year}_{month:02d}_{datetime.now():%Y%m%d_%H%M%S_%f}.pdf"
        output_path = self.output_dir / filename
        temporary_path = output_path.with_suffix(".tmp.pdf")
        document = SimpleDocTemplate(
            str(temporary_path),
            pagesize=landscape(A4),
            rightMargin=0.75 * cm,
            leftMargin=0.75 * cm,
            topMargin=0.7 * cm,
            bottomMargin=0.7 * cm,
        )

        story = [
            self._cover(client, year, month),
            Spacer(1, 0.18 * cm),
            self._calendar_table(posts, year, month),
            PageBreak(),
            Paragraph("Lista de Conteúdos", self.styles["Title"]),
            Spacer(1, 0.25 * cm),
            self._posts_table(posts),
            PageBreak(),
            Paragraph("Detalhes dos Conteúdos", self.styles["Title"]),
            Spacer(1, 0.25 * cm),
            *self._post_details(posts),
        ]
        try:
            document.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
            temporary_path.replace(output_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return output_path

    def _cover(self, client: Client, year: int, month: int) -> Table:
        data = [
            [Paragraph(f"Calendário Editorial - {MONTH_NAMES[month - 1]} {year}", self.styles["TitleWhite"])],
            [
                Paragraph(
                    f"<b>Cliente:</b> {self._escape(client.name)} &nbsp;&nbsp; "
                    f"<b>Nicho:</b> {self._escape(client.niche)} &nbsp;&nbsp; "
                    f"<b>Instagram:</b> {self._escape(client.instagram)}",
                    self.styles["CoverInfo"],
                )
            ],
            [Paragraph(f"<b>Objetivo:</b> {self._escape(client.objective)}", self.styles["CoverInfo"])],
        ]
        table = Table(data, colWidths=[27.6 * cm], rowHeights=[0.72 * cm, 0.52 * cm, 0.62 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#E5E7EB")),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#111827")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return table

    def _calendar_table(self, posts: list[Post], year: int, month: int) -> Table:
        by_day: dict[int, list[Post]] = defaultdict(list)
        for post in posts:
            by_day[int(post.post_date[-2:])].append(post)

        calendar.setfirstweekday(calendar.SUNDAY)
        weeks = calendar.monthcalendar(year, month)
        weekdays = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"]
        data = [[Paragraph(day, self.styles["WeekdayHeader"]) for day in weekdays]]

        for week in weeks:
            row = []
            for day in week:
                if day == 0:
                    row.append(Paragraph("", self.styles["CellText"]))
                    continue
                entries = [f"<b>{day}</b>"]
                for post in by_day.get(day, [])[:2]:
                    title = self._shorten(post.title, 26)
                    description = self._shorten(post.description, 44)
                    post_lines = f"{self._escape(post.content_type)}: {self._escape(title)}"
                    if description:
                        post_lines += f"<br/><font color='#475569'>{self._escape(description)}</font>"
                    entries.append(post_lines)
                if len(by_day.get(day, [])) > 2:
                    entries.append(f"+{len(by_day[day]) - 2} conteúdo(s)")
                row.append(Paragraph("<br/>".join(entries), self.styles["CellText"]))
            data.append(row)

        day_row_height = 2.55 * cm if len(weeks) <= 5 else 2.16 * cm
        table = Table(data, colWidths=[3.94 * cm] * 7, rowHeights=[0.52 * cm] + [day_row_height] * len(weeks))
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for row_index, week in enumerate(weeks, start=1):
            for col_index, day in enumerate(week):
                if day == 0:
                    style.append(("BACKGROUND", (col_index, row_index), (col_index, row_index), colors.HexColor("#F8FAFC")))
                elif by_day.get(day):
                    style.append(("BACKGROUND", (col_index, row_index), (col_index, row_index), colors.HexColor("#E0F2FE")))
        table.setStyle(TableStyle(style))
        return table

    def _posts_table(self, posts: list[Post]) -> Table:
        header = [Paragraph(f"<b>{value}</b>", self.styles["SmallMuted"]) for value in ["Data", "Tipo", "Plataforma", "Título", "Status"]]
        data = [header]
        for post in posts:
            data.append(
                [
                    Paragraph(self._escape(post.post_date), self.styles["SmallMuted"]),
                    Paragraph(self._escape(post.content_type), self.styles["SmallMuted"]),
                    Paragraph(self._escape(post.platform), self.styles["SmallMuted"]),
                    Paragraph(self._escape(post.title), self.styles["SmallMuted"]),
                    Paragraph(self._escape(post.status), self.styles["SmallMuted"]),
                ]
            )
        if len(data) == 1:
            data.append([Paragraph(value, self.styles["SmallMuted"]) for value in ["-", "-", "-", "Nenhum conteúdo cadastrado para este mês.", "-"]])

        table = Table(data, colWidths=[3 * cm, 3 * cm, 3 * cm, 12 * cm, 4 * cm], repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]
        for row_index, post in enumerate(posts, start=1):
            style.append(("TEXTCOLOR", (4, row_index), (4, row_index), STATUS_COLORS.get(post.status, colors.black)))
            style.append(("FONTNAME", (4, row_index), (4, row_index), "Helvetica-Bold"))
        table.setStyle(TableStyle(style))
        return table

    def _post_details(self, posts: list[Post]) -> list:
        if not posts:
            return [Paragraph("Nenhum conteúdo cadastrado para este mês.", self.styles["BodyText"])]
        blocks: list = []
        for post in posts:
            details = [
                Paragraph(f"<b>{self._escape(post.post_date)} · {self._escape(post.title)}</b>", self.styles["Heading3"]),
                Paragraph(f"<b>Tipo:</b> {self._escape(post.content_type)} &nbsp;&nbsp; <b>Plataforma:</b> {self._escape(post.platform)} &nbsp;&nbsp; <b>Status:</b> {self._escape(post.status)}", self.styles["BodyText"]),
                Paragraph(f"<b>Descrição:</b> {self._escape(post.description) or '—'}", self.styles["BodyText"]),
                Paragraph(f"<b>Legenda:</b> {self._escape(post.caption) or '—'}", self.styles["BodyText"]),
                Paragraph(f"<b>CTA:</b> {self._escape(post.cta) or '—'}", self.styles["BodyText"]),
                Spacer(1, 0.25 * cm),
            ]
            blocks.extend(details)
        return blocks

    @staticmethod
    def _footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawRightString(28.5 * cm, 0.55 * cm, f"Gerado em {date.today().strftime('%d/%m/%Y')}")
        canvas.restoreState()

    @staticmethod
    def _slug(value: str) -> str:
        valid = [char.lower() if char.isalnum() else "_" for char in value.strip()]
        return "".join(valid).strip("_") or "cliente"

    @staticmethod
    def _escape(value: str) -> str:
        return html.escape(value or "")

    @staticmethod
    def _shorten(value: str, limit: int) -> str:
        clean = " ".join((value or "").split())
        if len(clean) <= limit:
            return clean
        return f"{clean[: limit - 3].rstrip()}..."
