"""Word 计算书导出工具。"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT


def _add_dataframe_table(document: Document, df: pd.DataFrame) -> None:
    """将 DataFrame 写入 Word 表格。"""
    if len(df.columns) > 8:
        identity = [column for column in ("构件", "跨号", "截面编号", "截面名称", "全局工况") if column in df.columns][:2]
        remaining = [column for column in df.columns if column not in identity]
        for start in range(0, len(remaining), max(1, 8 - len(identity))):
            if start:
                document.add_paragraph("续表（同一数据表按列拆分）")
            _add_dataframe_table(document, df[identity + remaining[start:start + 8 - len(identity)]])
        return
    table = document.add_table(rows=1, cols=len(df.columns))
    table.style = "Table Grid"
    table.autofit = False
    for cell, column in zip(table.rows[0].cells, df.columns):
        cell.text = str(column)
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            cell.text = str(value)
    available_width = Inches(6.5)
    cell_width = int(available_width / max(len(df.columns), 1))
    for row in table.rows:
        for cell in row.cells:
            cell.width = cell_width
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)


def build_word_report(
    title: str,
    tables: dict[str, pd.DataFrame],
    notes: list[str] | None = None,
    images: dict[str, bytes] | None = None,
) -> bytes:
    """用 python-docx 和 BytesIO 生成 docx 半自动计算书。"""
    document = Document()
    document.add_heading(title, level=0)
    document.add_paragraph("课程名称：《水工钢筋混凝土》")
    document.add_paragraph("题目：整体式单向板肋形楼盖设计与辅助计算程序开发")
    document.add_heading("人工复核说明", level=1)
    document.add_paragraph("本计算书由程序半自动生成，结果不能替代课程设计手算、教材系数表和教师要求的人工复核。")
    document.add_paragraph("正式内力采用矩阵刚度法；荷载按同一全局工况由板支承线逐级传到次梁和主梁交点。支座中心与真实支座边缘分别保留。配筋和抗剪中的课程近似参数需人工按采用规范复核。")

    if notes:
        document.add_heading("已知不足和适用范围", level=1)
        for note in notes:
            document.add_paragraph(str(note), style="List Bullet")

    for heading, df in tables.items():
        document.add_heading(str(heading), level=1)
        _add_dataframe_table(document, df)

    if images:
        document.add_heading("矩阵刚度法图形成果", level=1)
        for heading, png in images.items():
            document.add_heading(str(heading), level=2)
            document.add_picture(BytesIO(png), width=Inches(6.4))

    output = BytesIO()
    document.save(output)
    return output.getvalue()
