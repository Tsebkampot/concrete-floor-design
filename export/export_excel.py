"""Excel 导出工具。"""

from __future__ import annotations

from io import BytesIO

import pandas as pd


def build_excel_workbook(tables: dict[str, pd.DataFrame]) -> bytes:
    """将多张 DataFrame 导出为一个 xlsx 文件。"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in tables.items():
            sheet_name = name[:31] or "Sheet"
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
            for column_cells in worksheet.columns:
                max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 42)
    return output.getvalue()
