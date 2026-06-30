"""旧版手算对比用简化包络（不参与正式设计）。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


LIVE_LOAD_PATTERNS = ["全跨活载", "奇数跨活载", "偶数跨活载", "单跨活载", "相邻跨活载"]


@dataclass(frozen=True)
class EnvelopeCurve:
    """某一活载布置下的控制点曲线。"""

    pattern: str
    positions: list[float]
    moments: list[float]
    shears: list[float]


def pattern_factor(pattern: str, section_index: int) -> float:
    """返回简化活载布置影响系数。

    说明：这是课程设计演示用的简化方法，不替代连续梁精确影响线分析。
    """
    if pattern == "全跨活载":
        return 1.0
    if pattern == "奇数跨活载":
        return 1.0 if section_index % 2 == 1 else 0.45
    if pattern == "偶数跨活载":
        return 1.0 if section_index % 2 == 0 else 0.45
    if pattern == "单跨活载":
        return 1.0 if section_index == 1 else 0.25
    if pattern == "相邻跨活载":
        return 1.0 if section_index in (1, 2) else 0.35
    raise ValueError(f"未知活载布置：{pattern}")


def calculate_envelope(
    dead_design_load: float,
    live_design_load: float,
    span_m: float,
    load_type: str = "line",
) -> tuple[list[EnvelopeCurve], pd.DataFrame]:
    """计算控制点最不利内力。

    ``load_type='line'`` 时荷载单位为 kN/m，弯矩按 ``qL2`` 取系数；
    ``load_type='point'`` 时荷载单位为 kN，弯矩按 ``PL`` 取系数。
    """
    if dead_design_load <= 0 or live_design_load < 0 or span_m <= 0:
        raise ValueError("恒载、活载和跨度取值不合理")
    positions = [0.0, span_m / 2, span_m]
    section_names = ["左支座", "跨中", "右支座"]
    moment_coeffs = [-1 / 11, 1 / 11, -1 / 11]
    shear_coeffs = [0.5, 0.0, -0.5]
    curves: list[EnvelopeCurve] = []
    raw_rows = []
    for pattern in LIVE_LOAD_PATTERNS:
        moments: list[float] = []
        shears: list[float] = []
        for idx, coeff in enumerate(moment_coeffs):
            factor = pattern_factor(pattern, idx)
            total = dead_design_load + live_design_load * factor
            if load_type == "point":
                moment = coeff * total * span_m * 2.75
                shear = shear_coeffs[idx] * total
            else:
                moment = coeff * total * span_m**2
                shear = shear_coeffs[idx] * total * span_m
            moments.append(moment)
            shears.append(shear)
            raw_rows.append([section_names[idx], pattern, moment, shear])
        curves.append(EnvelopeCurve(pattern, positions, moments, shears))

    raw_df = pd.DataFrame(raw_rows, columns=["截面位置", "活载布置", "弯矩 M (kN·m)", "剪力 V (kN)"])
    summary_rows = []
    for section in section_names:
        section_df = raw_df[raw_df["截面位置"] == section]
        max_pos = section_df.loc[section_df["弯矩 M (kN·m)"].idxmax()]
        max_neg = section_df.loc[section_df["弯矩 M (kN·m)"].idxmin()]
        max_shear = section_df.iloc[section_df["剪力 V (kN)"].abs().argmax()]
        controlling = max_pos if abs(max_pos["弯矩 M (kN·m)"]) >= abs(max_neg["弯矩 M (kN·m)"]) else max_neg
        summary_rows.append(
            [
                section,
                controlling["弯矩 M (kN·m)"],
                controlling["活载布置"],
                max_shear["剪力 V (kN)"],
                max_shear["活载布置"],
            ]
        )
    summary_df = pd.DataFrame(
        summary_rows,
        columns=["截面位置", "最不利弯矩 (kN·m)", "对应活载布置", "最不利剪力 (kN)", "对应剪力布置"],
    )
    return curves, summary_df
