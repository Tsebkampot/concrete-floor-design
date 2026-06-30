"""Excel 导出工具。"""

from __future__ import annotations

from io import BytesIO

import pandas as pd


def build_excel_workbook(tables: dict[str, pd.DataFrame], images: dict[str, bytes] | None = None) -> bytes:
    """将多张 DataFrame 导出为一个 xlsx 文件。"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        used_names: set[str] = set()
        for name, df in tables.items():
            base = name[:31] or "Sheet"
            sheet_name = base
            suffix = 2
            while sheet_name in used_names:
                tail = f"_{suffix}"
                sheet_name = f"{base[:31-len(tail)]}{tail}"
                suffix += 1
            used_names.add(sheet_name)
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
            for column_cells in worksheet.columns:
                max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
                worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 42)
        if images:
            from openpyxl.drawing.image import Image as ExcelImage
            from PIL import Image as PILImage

            image_sheet_base = "矩阵图形成果"
            image_sheet = image_sheet_base
            suffix = 2
            while image_sheet in used_names:
                tail = f"_{suffix}"
                image_sheet = f"{image_sheet_base[:31-len(tail)]}{tail}"
                suffix += 1
            worksheet = writer.book.create_sheet(image_sheet)
            row = 1
            for title, png in images.items():
                worksheet.cell(row=row, column=1, value=title)
                image = ExcelImage(BytesIO(png))
                image.width = 760
                with PILImage.open(BytesIO(png)) as source:
                    image.height = min(470, int(760 * source.height / source.width))
                worksheet.add_image(image, f"A{row + 1}")
                row += max(22, int(image.height / 20) + 3)
            worksheet.column_dimensions["A"].width = 110
    return output.getvalue()
