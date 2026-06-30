"""PDF 计算书导出工具。"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from export.report_summary import build_calculation_book_tables


def _register_fonts() -> str:
    font_name = "ChineseEmbedded"
    try:
        pdfmetrics.registerFont(TTFont(font_name, "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"))
    except Exception:
        font_name = "STSong-Light"
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(font_name))
        except Exception:
            pass
    return font_name


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("CnTitle", parent=base["Title"], fontName=font_name, fontSize=22, leading=30, alignment=1),
        "h1": ParagraphStyle("CnHeading1", parent=base["Heading1"], fontName=font_name, fontSize=15, leading=22, spaceBefore=10, spaceAfter=8),
        "h2": ParagraphStyle("CnHeading2", parent=base["Heading2"], fontName=font_name, fontSize=12, leading=18, spaceBefore=6, spaceAfter=4),
        "body": ParagraphStyle("CnBody", parent=base["BodyText"], fontName=font_name, fontSize=9, leading=14),
    }


def _paragraph(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(str(text).replace("\n", "<br/>"), style)


def _table_from_dataframe(df: pd.DataFrame, font_name: str, max_rows: int | None = None) -> Table:
    table_df = df.copy()
    if max_rows is not None:
        table_df = table_df.head(max_rows)
    # 宽表按列拆成续表，避免 17/22 列直接挤入 A4 竖版。
    max_columns = 7
    identity = [column for column in ("构件", "跨号", "截面编号", "截面名称", "全局工况") if column in table_df.columns][:2]
    remaining = [column for column in table_df.columns if column not in identity]
    chunks = [identity + remaining[i:i + max_columns - len(identity)] for i in range(0, len(remaining), max_columns - len(identity))] or [identity]
    body_style = ParagraphStyle("CnTableBody", fontName=font_name, fontSize=6.2, leading=8, wordWrap="CJK")
    header_style = ParagraphStyle("CnTableHeader", fontName=font_name, fontSize=6.4, leading=8, textColor=colors.white, wordWrap="CJK")
    data: list[list[Any]] = []
    header_rows: list[int] = []
    continuation_rows: list[int] = []
    def cell(value: Any, style: ParagraphStyle) -> Paragraph:
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)
    for chunk_index, columns in enumerate(chunks):
        if chunk_index:
            continuation_rows.append(len(data))
            data.append([cell("续表（同一数据表按列拆分）", body_style)] + [""] * (max_columns - 1))
        header_rows.append(len(data))
        data.append([cell(column, header_style) for column in columns] + [""] * (max_columns - len(columns)))
        for row in table_df[columns].to_numpy().tolist():
            data.append([cell(value, body_style) for value in row] + [""] * (max_columns - len(row)))
    if identity:
        widths = [18 * mm] * len(identity) + [(174 - 18 * len(identity)) * mm / (max_columns - len(identity))] * (max_columns - len(identity))
    else:
        widths = [174 * mm / max_columns] * max_columns
    table = Table(data, repeatRows=0, colWidths=widths, splitByRow=True)
    dynamic_styles = []
    for row_index in header_rows:
        dynamic_styles.extend([
            ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#0f4c81")),
            ("TEXTCOLOR", (0, row_index), (-1, row_index), colors.white),
        ])
    for row_index in continuation_rows:
        dynamic_styles.extend([
            ("SPAN", (0, row_index), (-1, row_index)),
            ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#e6eef5")),
        ])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8e3ec")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
            ] + dynamic_styles
        )
    )
    return table


def _draw_page_background(canvas, doc) -> None:
    """绘制白色页面背景和页码，避免部分渲染器显示透明黑底。"""
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#60758a"))
    canvas.setFont("ChineseEmbedded" if "ChineseEmbedded" in pdfmetrics.getRegisteredFontNames() else "STSong-Light", 8)
    canvas.drawRightString(width - 18 * mm, 8 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build_pdf_report(student_info: dict[str, str], params: dict[str, Any], tables: dict[str, pd.DataFrame], results: dict[str, Any]) -> bytes:
    """使用 reportlab 在内存中生成课程设计计算书 PDF。"""
    font_name = _register_fonts()
    styles = _styles(font_name)
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story: list[Any] = []

    project_name = student_info.get("project_name") or "整体式单向板肋形楼盖设计辅助计算书"
    report_date = student_info.get("date") or date.today().isoformat()
    story.append(_paragraph(project_name, styles["title"]))
    story.append(Spacer(1, 18))
    cover_rows = pd.DataFrame(
        [
            ["项目名称", project_name],
            ["学生姓名", student_info.get("student_name", "")],
            ["学号", student_info.get("student_id", "")],
            ["班级", student_info.get("class_name", "")],
            ["日期", report_date],
        ],
        columns=["项目", "内容"],
    )
    story.append(_table_from_dataframe(cover_rows, font_name))
    story.append(PageBreak())

    summary_tables = build_calculation_book_tables(params, tables, results)
    for index, (table_name, df) in enumerate(summary_tables.items(), start=1):
        story.append(_paragraph(f"{index}、{table_name}", styles["h1"]))
        story.append(_table_from_dataframe(df, font_name))
        story.append(Spacer(1, 8))
        if table_name == "计算数据总表":
            story.append(PageBreak())

    story.append(_paragraph("设计结论", styles["h1"]))
    story.append(
        _paragraph(
            "本计算书依据当前输入参数自动生成，报告正文按计算数据汇总表口径整理。完整节点、单元、刚度矩阵、支座反力、控制截面包络和图形数据请查看 Excel 结果表。梁跨中正弯矩按 T 形截面、支座负弯矩按矩形截面判断；翼缘有效宽度、抗剪、最小配筋、锚固、截断和构造钢筋仍需按采用规范及教师要求人工复核。",
            styles["body"],
        )
    )

    doc.build(story, onFirstPage=_draw_page_background, onLaterPages=_draw_page_background)
    return output.getvalue()
