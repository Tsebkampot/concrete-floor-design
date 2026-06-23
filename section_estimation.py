"""结构布置与截面尺寸初估。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SectionEstimate:
    """单个构件截面初估结果。"""

    member: str
    span_m: float
    h_min_mm: float
    h_max_mm: float
    b_min_mm: float
    b_max_mm: float
    adopted: str
    judgement: str
    suggestion: str


def judge_range(value: float, lower: float, upper: float, label: str) -> tuple[str, str]:
    """判断用户输入尺寸与推荐范围的关系。"""
    if value < lower:
        return "偏小", f"建议增大{label}，不宜小于 {lower:.0f} mm"
    if value > upper:
        return "偏大", f"{label}偏大，可结合净高、经济性和配筋复核"
    return "合理", "可作为课程设计初选尺寸，后续仍需按内力和构造复核"


def estimate_slab(h_mm: float) -> SectionEstimate:
    """板厚初估：课程设计默认 80 mm，建议范围 80-120 mm。"""
    judgement, suggestion = judge_range(h_mm, 80, 120, "板厚")
    return SectionEstimate(
        member="单向板",
        span_m=0,
        h_min_mm=80,
        h_max_mm=120,
        b_min_mm=1000,
        b_max_mm=1000,
        adopted=f"h={h_mm:.0f} mm，按 1 m 板带计算",
        judgement=judgement,
        suggestion=suggestion,
    )


def estimate_beam(
    member: str,
    span_m: float,
    adopted_b_mm: float,
    adopted_h_mm: float,
    h_ratio_min: float,
    h_ratio_max: float,
) -> SectionEstimate:
    """按连续梁经验范围估算梁高和梁宽。

    ``h_ratio_min`` 和 ``h_ratio_max`` 表示 ``h = L / ratio`` 的推荐分母。
    例如次梁为 ``1/18-1/12 L``，传入 18 和 12。
    """
    if span_m <= 0:
        raise ValueError("计算跨度必须大于 0")
    span_mm = span_m * 1000
    h_min = span_mm / h_ratio_min
    h_max = span_mm / h_ratio_max
    b_min = h_min / 3
    b_max = h_max / 2
    h_judgement, h_suggestion = judge_range(adopted_h_mm, h_min, h_max, "梁高")
    b_judgement, b_suggestion = judge_range(adopted_b_mm, adopted_h_mm / 3, adopted_h_mm / 2, "梁宽")
    if h_judgement == "合理" and b_judgement == "合理":
        judgement = "合理"
        suggestion = "截面尺寸满足经验初估范围，后续按配筋和挠度构造复核"
    else:
        judgement = "需调整" if "偏小" in (h_judgement, b_judgement) else "偏保守"
        suggestion = f"{h_suggestion}；{b_suggestion}"
    return SectionEstimate(
        member=member,
        span_m=span_m,
        h_min_mm=h_min,
        h_max_mm=h_max,
        b_min_mm=b_min,
        b_max_mm=b_max,
        adopted=f"b×h={adopted_b_mm:.0f}×{adopted_h_mm:.0f} mm",
        judgement=judgement,
        suggestion=suggestion,
    )


def estimate_all_sections(
    slab_h_mm: float,
    secondary_span_m: float,
    secondary_b_mm: float,
    secondary_h_mm: float,
    main_span_m: float,
    main_b_mm: float,
    main_h_mm: float,
) -> list[SectionEstimate]:
    """输出板、次梁、主梁的初估结果。"""
    return [
        estimate_slab(slab_h_mm),
        estimate_beam("次梁", secondary_span_m, secondary_b_mm, secondary_h_mm, 18, 12),
        estimate_beam("主梁", main_span_m, main_b_mm, main_h_mm, 15, 10),
    ]


def estimates_to_dataframe(estimates: list[SectionEstimate]) -> pd.DataFrame:
    """将截面初估结果转为 DataFrame。"""
    return pd.DataFrame(
        [
            [
                item.member,
                "-" if item.span_m == 0 else f"{item.span_m:.3f}",
                f"{item.h_min_mm:.0f}-{item.h_max_mm:.0f}",
                f"{item.b_min_mm:.0f}-{item.b_max_mm:.0f}",
                item.adopted,
                item.judgement,
                item.suggestion,
            ]
            for item in estimates
        ],
        columns=[
            "构件名称",
            "计算跨度 (m)",
            "推荐高度范围 (mm)",
            "推荐宽度范围 (mm)",
            "用户采用尺寸",
            "合理性判断",
            "修改建议",
        ],
    )
