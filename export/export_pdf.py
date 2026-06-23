"""PDF 计算书导出工具。"""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from calculations.load_combination import analyze_load_combinations
from calculations.moment_capacity import build_resisting_moment_points, calculate_moment_capacity
from calculations.rebar import recommend_longitudinal_rebar
from charts.plot_moment import figure_to_png_bytes, plot_moment_diagram
from charts.plot_resisting_moment import plot_resisting_moment_diagram
from charts.plot_shear import plot_shear_diagram


def _register_fonts() -> str:
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
    data = [[str(column) for column in table_df.columns]]
    data.extend([[str(value) for value in row] for row in table_df.to_numpy().tolist()])
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8e3ec")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
            ]
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
    canvas.setFont("STSong-Light", 8)
    canvas.drawRightString(width - 18 * mm, 8 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def _component_chart_bytes(results: dict[str, Any], member_key: str) -> tuple[bytes, bytes]:
    if member_key == "slab":
        result = results["slab"]
        labels = ["左支座", "跨中", "右支座"]
        xs = [0.0, result.input.l0_m / 2, result.input.l0_m]
        moments = [-abs(result.moment_kN_m) * 0.85, result.moment_kN_m, -abs(result.moment_kN_m) * 0.85]
        shears = [result.line_load_design_kN_m * result.input.l0_m * 0.5, 0.0, -result.line_load_design_kN_m * result.input.l0_m * 0.5]
        moment_kind = "quadratic"
        shear_mode = "linear"
        title_prefix = "板"
    elif member_key == "secondary":
        result = results["secondary"]
        labels = ["左支座", "跨中", "右支座"]
        xs = [0.0, result.input.l0_m / 2, result.input.l0_m]
        moments = [-abs(result.moment_kN_m) * 0.85, result.moment_kN_m, -abs(result.moment_kN_m) * 0.85]
        shears = [result.shear_kN, 0.0, -result.shear_kN]
        moment_kind = "quadratic"
        shear_mode = "linear"
        title_prefix = "次梁"
    else:
        result = results["main"]
        labels = ["左支座", "跨中", "右支座"]
        xs = [0.0, result.input.l0_m / 2, result.input.l0_m]
        moments = [-abs(result.moment_kN_m) * 0.85, result.moment_kN_m, -abs(result.moment_kN_m) * 0.85]
        shears = [result.shear_kN, 0.0, -result.shear_kN]
        moment_kind = "control_polyline"
        shear_mode = "step"
        title_prefix = "主梁"
    moment_chart = plot_moment_diagram(xs, moments, labels, f"{title_prefix}弯矩图", curve_kind=moment_kind)
    shear_chart = plot_shear_diagram(xs, shears, labels, f"{title_prefix}剪力图", mode=shear_mode)
    return figure_to_png_bytes(moment_chart), figure_to_png_bytes(shear_chart)


def _resisting_chart_bytes(results: dict[str, Any], member_key: str) -> bytes:
    result = results["secondary"] if member_key == "secondary" else results["main"]
    positive_option = next((item for item in result.longitudinal_options if item.is_ok), result.longitudinal_options[-1])
    negative_option = next((item for item in recommend_longitudinal_rebar(result.required_as_mm2 * 1.05) if item.is_ok), positive_option)
    positive_mu = calculate_moment_capacity(positive_option.area_mm2, result.input.fc, result.input.fy, result.input.b_mm, result.input.h0_mm)
    negative_mu = calculate_moment_capacity(negative_option.area_mm2, result.input.fc, result.input.fy, result.input.b_mm, result.input.h0_mm)
    points = build_resisting_moment_points(result.input.l0_m, abs(result.moment_kN_m), -abs(result.moment_kN_m) * 0.85, positive_mu, negative_mu)
    chart = plot_resisting_moment_diagram(
        [p.x_m for p in points],
        [p.design_moment_kN_m for p in points],
        [p.capacity_kN_m for p in points],
        [p.position for p in points],
        "简化抵抗弯矩图",
    )
    return figure_to_png_bytes(chart)


def _combination_chart_bytes(results: dict[str, Any], member: str) -> tuple[bytes, bytes]:
    analysis = analyze_load_combinations(member, results)
    labels = analysis.moment_envelope_df["截面位置"].tolist()
    xs = analysis.moment_envelope_df["x (m)"].astype(float).tolist()
    moments = analysis.moment_envelope_df["最大弯矩包络 (kN·m)"].astype(float).tolist()
    shears = analysis.shear_envelope_df["最大剪力包络 (kN)"].astype(float).tolist()
    moment_chart = plot_moment_diagram(xs, moments, labels, f"{member}最大弯矩包络图")
    shear_chart = plot_shear_diagram(xs, shears, labels, f"{member}最大剪力包络图")
    return figure_to_png_bytes(moment_chart), figure_to_png_bytes(shear_chart)


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
    for table_name in ["板荷载", "次梁荷载", "主梁荷载", "截面尺寸初估"]:
        story.append(_paragraph(table_name, styles["h2"]))
        story.append(_table_from_dataframe(tables[table_name], font_name))
        story.append(Spacer(1, 6))

    story.append(PageBreak())
    component_sections = [
        ("三、板计算过程", "slab", ["板荷载", "板内力与配筋", "板推荐配筋"]),
        ("四、次梁计算过程", "secondary", ["次梁荷载", "次梁内力与配筋", "次梁推荐纵筋", "次梁推荐箍筋"]),
        ("五、主梁计算过程", "main", ["主梁荷载", "主梁内力与配筋", "主梁推荐纵筋", "主梁推荐箍筋"]),
    ]
    for heading, key, table_names in component_sections:
        story.append(_paragraph(heading, styles["h1"]))
        for table_name in table_names:
            story.append(_paragraph(table_name, styles["h2"]))
            story.append(_table_from_dataframe(tables[table_name], font_name))
            story.append(Spacer(1, 5))
        moment_png, shear_png = _component_chart_bytes(results, key)
        story.append(_paragraph("弯矩图", styles["h2"]))
        story.append(_image_from_png(moment_png))
        story.append(_paragraph("剪力图", styles["h2"]))
        story.append(_image_from_png(shear_png))
        story.append(PageBreak())

    story.append(_paragraph("六、最不利荷载组合与包络图", styles["h1"]))
    for member in ["板", "次梁", "主梁"]:
        analysis = analyze_load_combinations(member, results)
        story.append(_paragraph(f"{member}最不利荷载组合", styles["h2"]))
        story.append(_table_from_dataframe(analysis.summary_df, font_name))
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
    for table_name in ["板推荐配筋", "次梁推荐纵筋", "次梁推荐箍筋", "主梁推荐纵筋", "主梁推荐箍筋"]:
        story.append(_paragraph(table_name, styles["h2"]))
        story.append(_table_from_dataframe(tables[table_name], font_name))
        story.append(Spacer(1, 5))

    story.append(_paragraph("八、设计结论", styles["h1"]))
    story.append(
        _paragraph(
            "本计算书依据当前输入参数自动生成，完成了板、次梁、主梁的荷载计算、内力计算、配筋计算、图形展示和最不利荷载组合分析。程序结果用于课程设计辅助整理，最终提交前仍应结合教材、规范和教师要求进行人工复核。",
            styles["body"],
        )
    )

    doc.build(story, onFirstPage=_draw_page_background, onLaterPages=_draw_page_background)
    return output.getvalue()
