"""旧版手算对比用简化控制点内力计算（不参与正式设计）。

本模块用于绘图和包络分析。它采用课程设计展示用的控制点方法：
支座、跨中和中间支座按经验系数取值，实际连续梁内力系数应以教材
或教师指定表格为准。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ForcePoint:
    """控制截面内力点。"""

    position: str
    x_m: float
    moment_kN_m: float
    shear_kN: float


def line_load_control_points(q_kN_m: float, span_m: float, negative_factor: float = -1 / 11) -> list[ForcePoint]:
    """按均布荷载生成简化弯矩、剪力控制点。"""
    if q_kN_m <= 0 or span_m <= 0:
        raise ValueError("线荷载和跨度必须大于 0")
    positive_m = q_kN_m * span_m**2 / 11
    negative_m = negative_factor * q_kN_m * span_m**2
    end_v = 0.5 * q_kN_m * span_m
    return [
        ForcePoint("左支座", 0.0, negative_m, end_v),
        ForcePoint("跨中", span_m / 2, positive_m, 0.0),
        ForcePoint("右支座", span_m, negative_m, -end_v),
    ]


def point_load_control_points(p_kN: float, span_m: float, negative_factor: float = -0.125) -> list[ForcePoint]:
    """按集中荷载生成简化弯矩、剪力控制点。"""
    if p_kN <= 0 or span_m <= 0:
        raise ValueError("集中荷载和跨度必须大于 0")
    positive_m = 0.25 * p_kN * span_m
    negative_m = negative_factor * p_kN * span_m
    end_v = 0.5 * p_kN
    return [
        ForcePoint("左支座", 0.0, negative_m, end_v),
        ForcePoint("跨中", span_m / 2, positive_m, 0.0),
        ForcePoint("右支座", span_m, negative_m, -end_v),
    ]


def force_points_to_dataframe(points: list[ForcePoint]) -> pd.DataFrame:
    """将控制点内力转成表格。"""
    return pd.DataFrame(
        [[p.position, p.x_m, p.moment_kN_m, p.shear_kN] for p in points],
        columns=["截面位置", "x (m)", "弯矩 M (kN·m)", "剪力 V (kN)"],
    )
