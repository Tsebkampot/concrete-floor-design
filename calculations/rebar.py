"""钢筋面积与常用配筋方案计算。"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RebarOption:
    """单个配筋方案的计算结果。"""

    name: str
    diameter_mm: float
    spacing_mm: float
    area_mm2_per_m: float
    is_ok: bool
    over_ratio_percent: float = 0.0
    evaluation: str = "不足"


@dataclass(frozen=True)
class LongitudinalOption:
    """梁纵向受力钢筋方案。"""

    name: str
    count: int
    diameter_mm: float
    area_mm2: float
    is_ok: bool
    over_ratio_percent: float
    evaluation: str


@dataclass(frozen=True)
class StirrupRecommendation:
    """箍筋推荐方案。"""

    name: str
    diameter_mm: float
    legs: int
    spacing_mm: float
    av_over_s_mm2_per_mm: float
    is_ok: bool
    evaluation: str


def bar_area(diameter_mm: float) -> float:
    """计算单根圆钢筋截面积，单位 mm2。"""
    if diameter_mm <= 0:
        raise ValueError("钢筋直径必须大于 0")
    return math.pi * diameter_mm**2 / 4


def rebar_area_per_meter(diameter_mm: float, spacing_mm: float) -> float:
    """
    计算 1 m 板带内实配钢筋面积，单位 mm2/m。

    换算说明：
    1 m = 1000 mm，因此每米钢筋根数约为 1000 / spacing_mm。
    """
    if spacing_mm <= 0:
        raise ValueError("钢筋间距必须大于 0")
    return bar_area(diameter_mm) * 1000 / spacing_mm


def over_reinforcement_ratio(provided: float, required: float) -> float:
    """计算超配率，单位为百分数。"""
    if required <= 0:
        raise ValueError("计算所需面积必须大于 0")
    return (provided - required) / required * 100


def evaluate_rebar(provided: float, required: float) -> tuple[bool, float, str]:
    """判断配筋是否满足并给出评价。"""
    ratio = over_reinforcement_ratio(provided, required)
    if provided < required:
        return False, ratio, "不足"
    if ratio > 30:
        return True, ratio, "偏保守，建议复核"
    return True, ratio, "合理"


def check_rebar_options(
    required_as_mm2_per_m: float,
    options: list[tuple[float, float]] | None = None,
) -> list[RebarOption]:
    """根据所需钢筋面积，判断常用配筋方案是否满足要求。"""
    if required_as_mm2_per_m < 0:
        raise ValueError("所需钢筋面积不能为负数")

    if options is None:
        options = [
            (8, 200),
            (8, 150),
            (10, 200),
            (10, 150),
            (12, 200),
        ]

    results: list[RebarOption] = []
    for diameter, spacing in options:
        actual_area = rebar_area_per_meter(diameter, spacing)
        is_ok, over_ratio, evaluation = evaluate_rebar(actual_area, required_as_mm2_per_m)
        results.append(
            RebarOption(
                name=f"φ{int(diameter)}@{int(spacing)}",
                diameter_mm=diameter,
                spacing_mm=spacing,
                area_mm2_per_m=actual_area,
                is_ok=is_ok,
                over_ratio_percent=over_ratio,
                evaluation=evaluation,
            )
        )
    return results


def recommend_longitudinal_rebar(
    required_as_mm2: float,
    options: list[tuple[int, int]] | None = None,
) -> list[LongitudinalOption]:
    """推荐常见梁纵筋方案。"""
    if required_as_mm2 < 0:
        raise ValueError("所需纵筋面积不能为负数")
    if required_as_mm2 == 0:
        required_as_mm2 = 1e-9
    if options is None:
        options = [(2, 12), (2, 14), (2, 16), (3, 16), (2, 18), (3, 18), (2, 20), (3, 20), (2, 22), (3, 22)]
    results: list[LongitudinalOption] = []
    for count, diameter in options:
        area = count * bar_area(diameter)
        is_ok, over_ratio, evaluation = evaluate_rebar(area, required_as_mm2)
        results.append(
            LongitudinalOption(
                name=f"{count}φ{diameter}",
                count=count,
                diameter_mm=diameter,
                area_mm2=area,
                is_ok=is_ok,
                over_ratio_percent=over_ratio,
                evaluation=evaluation,
            )
        )
    return results


def recommend_stirrups(required_av_over_s: float) -> list[StirrupRecommendation]:
    """推荐常见双肢箍筋方案。

    当规范最小配箍参数不足时，本函数只对 ``Av/s`` 进行面积间距比判断，
    并在评价中提示需人工按教材或规范复核。
    """
    if required_av_over_s < 0:
        raise ValueError("所需箍筋面积间距比不能为负数")
    required = required_av_over_s if required_av_over_s > 0 else 1e-9
    options = [(6, 2, 200), (6, 2, 150), (8, 2, 200), (8, 2, 150), (8, 2, 100)]
    results: list[StirrupRecommendation] = []
    for diameter, legs, spacing in options:
        av_over_s = legs * bar_area(diameter) / spacing
        is_ok = av_over_s >= required_av_over_s
        if not is_ok:
            evaluation = "不足"
        elif spacing > 200:
            evaluation = "间距偏大，需人工复核"
        else:
            evaluation = "满足面积要求，需人工按教材/规范复核最小构造"
        results.append(
            StirrupRecommendation(
                name=f"{legs}肢φ{diameter}@{spacing}",
                diameter_mm=diameter,
                legs=legs,
                spacing_mm=spacing,
                av_over_s_mm2_per_mm=av_over_s,
                is_ok=is_ok,
                evaluation=evaluation,
            )
        )
    return results
