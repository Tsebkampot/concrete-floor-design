"""半自动计算书 Markdown 导出。"""

from __future__ import annotations

import pandas as pd


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """DataFrame 转 Markdown 表格。"""
    return df.to_markdown(index=False)


def build_markdown_report(title: str, tables: dict[str, pd.DataFrame], notes: list[str] | None = None) -> str:
    """生成半自动计算书 Markdown 文本。"""
    parts = [
        f"# {title}",
        "",
        "## 封面占位",
        "",
        "- 课程名称：《水工钢筋混凝土》",
        "- 题目：整体式单向板肋形楼盖设计与辅助计算程序开发",
        "- 小组成员及分工：待填写",
        "",
        "## 人工复核说明",
        "",
        "本计算书由程序半自动生成，结果不能替代课程设计手算和教师要求的复核。",
    ]
    if notes:
        parts.extend(["", "## 已知不足和适用范围", ""])
        parts.extend([f"- {note}" for note in notes])
    for heading, df in tables.items():
        parts.extend(["", f"## {heading}", "", dataframe_to_markdown(df)])
    return "\n".join(parts)
