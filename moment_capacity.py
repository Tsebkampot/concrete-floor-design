"""抵抗弯矩图计算。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MomentCapacityPoint:
    """设计弯矩和抵抗弯矩控制点。"""

    position: str
    x_m: float
    design_moment_kN_m: float
    capacity_kN_m: float
    judgement: str


def calculate_moment_capacity(as_mm2: float, fc: float, fy: float, b_mm: float, h0_mm: float) -> float:
    """按单筋矩形截面简化公式估算抗弯承载力 ``Mu``。

    ``x = fy * As / (fc * b)``，``Mu = fy * As * (h0 - x/2)``。
    输入单位为 N、mm，输出由 N·mm 换算为 kN·m。
    """
    if min(as_mm2, fc, fy, b_mm, h0_mm) <= 0:
        raise ValueError("As、fc、fy、b、h0 均必须大于 0")
    x_mm = fy * as_mm2 / (fc * b_mm)
    lever_arm = h0_mm - x_mm / 2
    if lever_arm <= 0:
        raise ValueError("受压区高度过大，当前截面不适合该简化公式")
    return fy * as_mm2 * lever_arm / 1_000_000


def build_resisting_moment_points(
    span_m: float,
    positive_design_moment: float,
    negative_design_moment: float,
    positive_capacity: float,
    negative_capacity: float,
) -> list[MomentCapacityPoint]:
    """生成支座负筋、跨中正筋的简化抵抗弯矩控制点。"""
    if span_m <= 0:
        raise ValueError("跨度必须大于 0")
    values = [
        ("左支座负筋范围", 0.0, negative_design_moment, -abs(negative_capacity)),
        ("跨中正筋范围", span_m / 2, positive_design_moment, abs(positive_capacity)),
        ("右支座负筋范围", span_m, negative_design_moment, -abs(negative_capacity)),
    ]
    points: list[MomentCapacityPoint] = []
    for name, x_m, design, capacity in values:
        ok = abs(capacity) >= abs(design)
        points.append(MomentCapacityPoint(name, x_m, design, capacity, "满足" if ok else "可能不足，需调整配筋"))
    return points


def resisting_points_to_dataframe(points: list[MomentCapacityPoint]) -> pd.DataFrame:
    """输出抵抗弯矩说明表。"""
    return pd.DataFrame(
        [[p.position, p.x_m, p.design_moment_kN_m, p.capacity_kN_m, p.judgement] for p in points],
        columns=["区段", "x (m)", "设计弯矩 M (kN·m)", "抵抗弯矩 Mu (kN·m)", "判断"],
    )
