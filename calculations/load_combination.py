"""最不利荷载组合分析。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


LOAD_PATTERNS = [
    "全跨布置",
    "隔跨布置",
    "奇跨布置",
    "偶跨布置",
    "单跨布置",
    "多跨最不利布置",
]

SECTION_NAMES = ["左支座", "跨中", "右支座"]
SECTION_POSITIONS = [0.0, 0.5, 1.0]
MOMENT_COEFFS = [-1 / 11, 1 / 11, -1 / 11]
SHEAR_COEFFS = [0.5, 0.0, -0.5]


@dataclass(frozen=True)
class LoadCombinationResult:
    """构件最不利荷载组合分析结果。"""

    member: str
    comparison_df: pd.DataFrame
    summary_df: pd.DataFrame
    moment_envelope_df: pd.DataFrame
    shear_envelope_df: pd.DataFrame
    controlling_pattern: str
    controlling_moment: float
    controlling_shear: float
    controlling_layout: str
    moment_explanation: str
    shear_explanation: str


def _pattern_factor(pattern: str, section_index: int) -> float:
    """返回课程设计展示用的简化活载影响系数。"""
    if pattern == "全跨布置":
        return 1.0
    if pattern == "隔跨布置":
        return 1.0 if section_index in (0, 2) else 0.45
    if pattern == "奇跨布置":
        return 1.0 if section_index in (1, 2) else 0.5
    if pattern == "偶跨布置":
        return 1.0 if section_index in (0, 1) else 0.5
    if pattern == "单跨布置":
        return 1.0 if section_index == 1 else 0.25
    if pattern == "多跨最不利布置":
        return [0.95, 1.0, 0.95][section_index]
    raise ValueError(f"未知活载布置：{pattern}")


def _load_label(pattern: str) -> str:
    labels = {
        "全跨布置": "各跨均布活荷载",
        "隔跨布置": "隔跨布置活荷载，突出支座负弯矩",
        "奇跨布置": "奇数跨布置活荷载",
        "偶跨布置": "偶数跨布置活荷载",
        "单跨布置": "单跨布置活荷载，突出跨中正弯矩",
        "多跨最不利布置": "按控制截面组合多跨活荷载",
    }
    return labels[pattern]


def _member_loads(member: str, results: dict) -> tuple[float, float, float, str]:
    if member == "板":
        slab = results["slab"]
        return (
            slab.dead_load_design_kN_m2 * slab.input.strip_width_m,
            slab.live_load_design_kN_m2 * slab.input.strip_width_m,
            slab.input.l0_m,
            "line",
        )
    if member == "次梁":
        secondary = results["secondary"]
        return secondary.dead_load_design_kN_m, secondary.live_load_design_kN_m, secondary.input.l0_m, "line"
    if member == "主梁":
        main = results["main"]
        return main.dead_load_design_kN, main.live_load_design_kN, main.input.l0_m, "point"
    raise ValueError(f"未知构件：{member}")


def _moment_and_shear(dead_load: float, live_load: float, factor: float, span_m: float, load_type: str, section_index: int) -> tuple[float, float]:
    total_load = dead_load + live_load * factor
    if load_type == "point":
        moment = MOMENT_COEFFS[section_index] * total_load * span_m * 2.75
        shear = SHEAR_COEFFS[section_index] * total_load
    else:
        moment = MOMENT_COEFFS[section_index] * total_load * span_m**2
        shear = SHEAR_COEFFS[section_index] * total_load * span_m
    return moment, shear


def _moment_explanation(section: str, value: float) -> str:
    if section == "跨中" and value >= 0:
        return "该工况控制跨中正弯矩"
    if "支座" in section and value < 0:
        return "该工况控制支座负弯矩"
    return "该工况控制该截面弯矩"


def analyze_load_combinations(member: str, results: dict) -> LoadCombinationResult:
    """分析构件在不同活载布置下的最不利内力。"""
    dead_load, live_load, span_m, load_type = _member_loads(member, results)
    rows = []
    for pattern in LOAD_PATTERNS:
        for idx, section in enumerate(SECTION_NAMES):
            factor = _pattern_factor(pattern, idx)
            moment, shear = _moment_and_shear(dead_load, live_load, factor, span_m, load_type, idx)
            rows.append(
                {
                    "构件": member,
                    "工况名称": pattern,
                    "荷载布置方式": _load_label(pattern),
                    "截面位置": section,
                    "x (m)": round(SECTION_POSITIONS[idx] * span_m, 3),
                    "活载影响系数": round(factor, 3),
                    "支座负弯矩 (kN·m)": round(moment if moment < 0 else 0.0, 4),
                    "跨中正弯矩 (kN·m)": round(moment if moment > 0 else 0.0, 4),
                    "弯矩 M (kN·m)": round(moment, 4),
                    "剪力 V (kN)": round(shear, 4),
                }
            )
    comparison_df = pd.DataFrame(rows)

    summary_rows = []
    for section in SECTION_NAMES:
        section_df = comparison_df[comparison_df["截面位置"] == section]
        moment_row = section_df.loc[section_df["弯矩 M (kN·m)"].abs().idxmax()]
        shear_row = section_df.loc[section_df["剪力 V (kN)"].abs().idxmax()]
        summary_rows.append(
            {
                "截面位置": section,
                "最不利工况名称": moment_row["工况名称"],
                "控制弯矩 (kN·m)": moment_row["弯矩 M (kN·m)"],
                "控制剪力 (kN)": shear_row["剪力 V (kN)"],
                "对应荷载布置方式": moment_row["荷载布置方式"],
                "工程解释": _moment_explanation(section, float(moment_row["弯矩 M (kN·m)"])),
            }
        )
    summary_df = pd.DataFrame(summary_rows)

    moment_envelope_rows = []
    shear_envelope_rows = []
    for section in SECTION_NAMES:
        section_df = comparison_df[comparison_df["截面位置"] == section]
        moment_row = section_df.loc[section_df["弯矩 M (kN·m)"].abs().idxmax()]
        shear_row = section_df.loc[section_df["剪力 V (kN)"].abs().idxmax()]
        moment_envelope_rows.append(
            {
                "截面位置": section,
                "x (m)": moment_row["x (m)"],
                "最大弯矩包络 (kN·m)": moment_row["弯矩 M (kN·m)"],
                "控制工况": moment_row["工况名称"],
            }
        )
        shear_envelope_rows.append(
            {
                "截面位置": section,
                "x (m)": shear_row["x (m)"],
                "最大剪力包络 (kN)": shear_row["剪力 V (kN)"],
                "控制工况": shear_row["工况名称"],
            }
        )
    moment_envelope_df = pd.DataFrame(moment_envelope_rows)
    shear_envelope_df = pd.DataFrame(shear_envelope_rows)

    controlling_moment_row = comparison_df.loc[comparison_df["弯矩 M (kN·m)"].abs().idxmax()]
    controlling_shear_row = comparison_df.loc[comparison_df["剪力 V (kN)"].abs().idxmax()]
    return LoadCombinationResult(
        member=member,
        comparison_df=comparison_df,
        summary_df=summary_df,
        moment_envelope_df=moment_envelope_df,
        shear_envelope_df=shear_envelope_df,
        controlling_pattern=str(controlling_moment_row["工况名称"]),
        controlling_moment=float(controlling_moment_row["弯矩 M (kN·m)"]),
        controlling_shear=float(controlling_shear_row["剪力 V (kN)"]),
        controlling_layout=str(controlling_moment_row["荷载布置方式"]),
        moment_explanation=_moment_explanation(str(controlling_moment_row["截面位置"]), float(controlling_moment_row["弯矩 M (kN·m)"])),
        shear_explanation=f"该工况控制{controlling_shear_row['截面位置']}剪力",
    )
