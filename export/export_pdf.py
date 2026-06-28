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
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from calculations.moment_capacity import build_resisting_moment_points, calculate_moment_capacity
from calculations.rebar import recommend_longitudinal_rebar
from charts.plot_moment import figure_to_png_bytes, plot_moment_diagram
from charts.plot_resisting_moment import plot_resisting_moment_diagram
from charts.plot_shear import plot_shear_diagram
from charts.plot_control_sections import plot_control_section_diagram
from charts.plot_force_envelope import plot_matrix_moment_envelope, plot_matrix_shear_envelope


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


def _image_from_png(png_bytes: bytes, width_mm: float = 170) -> Image:
    stream = BytesIO(png_bytes)
    image = Image(stream)
    image._restrictSize(width_mm * mm, 86 * mm)
    return image


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


def _component_chart_bytes(results: dict[str, Any], member_key: str) -> tuple[bytes, bytes, bytes]:
    matrix = getattr(results["matrix"], member_key)
    control = plot_control_section_diagram(matrix)
    moment = plot_matrix_moment_envelope(matrix)
    shear = plot_matrix_shear_envelope(matrix)
    return figure_to_png_bytes(control), figure_to_png_bytes(moment), figure_to_png_bytes(shear)


def _resisting_chart_bytes(results: dict[str, Any], member_key: str) -> bytes:
    result = results[member_key]
    design = getattr(results["matrix"], f"{member_key}_design_df")
    capacities = []
    for _, row in design.iterrows():
        area = float(row["实配面积 (mm2)"])
        capacity = calculate_moment_capacity(area, result.input.fc, result.input.fy, result.input.b_mm, result.input.h0_mm) if area > 0 else 0.0
        capacities.append(-capacity if row["设计方向"] == "负弯矩" else capacity)
    chart = plot_resisting_moment_diagram(
        design["x (m)"].astype(float).tolist(),
        design["M (kN·m)"].astype(float).tolist(),
        capacities,
        [f"{row['截面编号']}-{row['设计方向']}" for _, row in design.iterrows()],
        "逐控制截面抵抗弯矩图",
    )
    return figure_to_png_bytes(chart)


def _combination_chart_bytes(results: dict[str, Any], member: str) -> tuple[bytes, bytes]:
    matrix = {"板": results["matrix"].slab, "次梁": results["matrix"].secondary, "主梁": results["matrix"].main}[member]
    return figure_to_png_bytes(plot_matrix_moment_envelope(matrix)), figure_to_png_bytes(plot_matrix_shear_envelope(matrix))


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

    story.append(_paragraph("一、基本参数", styles["h1"]))
    story.append(_table_from_dataframe(tables["基本参数"], font_name, max_rows=32))
    story.append(_paragraph("二、楼盖尺寸、荷载参数和材料参数", styles["h1"]))
    for table_name in ["板荷载", "矩阵荷载逐级传递", "截面尺寸初估"]:
        story.append(_paragraph(table_name, styles["h2"]))
        story.append(_table_from_dataframe(tables[table_name], font_name))
        story.append(Spacer(1, 6))

    story.append(PageBreak())
    component_sections = [
        ("三、板矩阵刚度计算", "slab", ["板矩阵荷载表", "板总刚度矩阵摘要", "板支座反力表", "板控制截面内力包络表", "板逐控制截面配筋表"]),
        ("四、次梁矩阵刚度计算", "secondary", ["次梁矩阵荷载表", "次梁总刚度矩阵摘要", "次梁支座反力表", "次梁控制截面内力包络表", "次梁逐控制截面配筋表"]),
        ("五、主梁矩阵刚度计算", "main", ["主梁矩阵荷载表", "主梁总刚度矩阵摘要", "主梁支座反力表", "主梁控制截面内力包络表", "主梁逐控制截面配筋表"]),
    ]
    for heading, key, table_names in component_sections:
        story.append(_paragraph(heading, styles["h1"]))
        for table_name in table_names:
            story.append(_paragraph(table_name, styles["h2"]))
            story.append(_table_from_dataframe(tables[table_name], font_name, max_rows=30))
            story.append(Spacer(1, 5))
        control_png, moment_png, shear_png = _component_chart_bytes(results, key)
        direction_title = {"slab": "板控制截面示意图（板计算方向）", "secondary": "次梁控制截面示意图（30m方向）", "main": "主梁控制截面示意图（18m方向）"}[key]
        story.append(_paragraph(direction_title, styles["h2"]))
        story.append(_image_from_png(control_png))
        story.append(_paragraph("弯矩图", styles["h2"]))
        story.append(_image_from_png(moment_png))
        story.append(_paragraph("剪力图", styles["h2"]))
        story.append(_image_from_png(shear_png))
        story.append(PageBreak())

    story.append(_paragraph("六、最不利荷载组合与包络图", styles["h1"]))
    for member in ["板", "次梁", "主梁"]:
        story.append(_paragraph(f"{member}最不利荷载组合", styles["h2"]))
        story.append(_table_from_dataframe(tables[f"{member}控制截面内力包络表"], font_name, max_rows=30))
        moment_png, shear_png = _combination_chart_bytes(results, member)
        story.append(_paragraph("最大弯矩包络图", styles["h2"]))
        story.append(_image_from_png(moment_png))
        story.append(_paragraph("最大剪力包络图", styles["h2"]))
        story.append(_image_from_png(shear_png))
        story.append(Spacer(1, 8))

    story.append(PageBreak())
    story.append(_paragraph("七、抵抗弯矩图与配筋汇总", styles["h1"]))
    for member_name, key in [("次梁", "secondary"), ("主梁", "main")]:
        story.append(_paragraph(f"{member_name}抵抗弯矩图", styles["h2"]))
        story.append(_image_from_png(_resisting_chart_bytes(results, key)))
    for table_name in ["板逐控制截面配筋表", "次梁逐控制截面配筋表", "主梁逐控制截面配筋表"]:
        story.append(_paragraph(table_name, styles["h2"]))
        story.append(_table_from_dataframe(tables[table_name], font_name))
        story.append(Spacer(1, 5))

    story.append(_paragraph("八、设计结论", styles["h1"]))
    story.append(
        _paragraph(
            "本计算书依据当前输入参数自动生成。板、次梁、主梁采用 Euler-Bernoulli 梁单元矩阵刚度法计算内力；同一全局工况中，板带支座反力除以板带宽度后逐支承线传给次梁，次梁支座反力再按实际交点传给主梁。控制截面同时保留支座中心与真实支座边缘，支座中心用于负弯矩检查，边缘用于面内弯矩和剪力检查。梁跨中正弯矩按 T 形截面、支座负弯矩按矩形截面判断；翼缘有效宽度、抗剪和构造参数仍按课程近似值估算，需人工按采用规范复核。当前正式逐线传力仅支持规则等跨楼盖。",
            styles["body"],
        )
    )

    doc.build(story, onFirstPage=_draw_page_background, onLaterPages=_draw_page_background)
    return output.getvalue()
