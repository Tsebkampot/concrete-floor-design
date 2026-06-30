"""课程设计系数法/手算对照计算链。

本模块独立于矩阵刚度法，用于复现小组新表中的板、次梁和主梁手算口径。
主梁同时保留 300x600 修正恒载与截图原始恒载，避免两套口径混用。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from calculations.slab import calculate_required_as


SCREENSHOT_LOAD_CASE = "截图原始口径（复现补充页）"
CORRECTED_LOAD_CASE = "300×600修正口径"


@dataclass(frozen=True)
class CourseDesignResult:
    """课程设计系数法结果表集合。"""

    slab_forces_df: pd.DataFrame
    secondary_forces_df: pd.DataFrame
    main_load_cases_df: pd.DataFrame
    main_forces_df: pd.DataFrame
    rebar_df: pd.DataFrame
    review_df: pd.DataFrame


def _round(value: float, digits: int = 5) -> float:
    return round(float(value), digits)


def _line_loads(params: dict) -> dict[str, float]:
    gamma_g = float(params["gamma_g"]) * float(params.get("importance_factor", 1.0))
    gamma_q = float(params["gamma_q"]) * float(params.get("importance_factor", 1.0))
    slab_dead_standard = (
        float(params["slab_h_mm"]) / 1000 * float(params["concrete_unit_weight"])
        + float(params["terrazzo_load"])
        + float(params["plaster_thickness_mm"]) / 1000 * float(params["plaster_unit_weight"])
    )
    slab_dead_design = gamma_g * slab_dead_standard
    slab_live_design = gamma_q * float(params["live_load"])

    secondary_rib_height = (float(params["secondary_h_mm"]) - float(params["slab_h_mm"])) / 1000
    secondary_dead_standard = (
        slab_dead_standard * float(params["secondary_beam_spacing_m"])
        + float(params["concrete_unit_weight"]) * float(params["secondary_b_mm"]) / 1000 * secondary_rib_height
        + float(params["plaster_unit_weight"]) * float(params["plaster_thickness_mm"]) / 1000 * secondary_rib_height * 2
    )
    secondary_dead_design = gamma_g * secondary_dead_standard
    secondary_live_design = gamma_q * float(params["live_load"]) * float(params["secondary_beam_spacing_m"])

    main_rib_height = (float(params["main_h_mm"]) - float(params["slab_h_mm"])) / 1000
    main_dead_corrected = (
        secondary_dead_design * float(params["main_beam_spacing_m"])
        + gamma_g * float(params["concrete_unit_weight"]) * float(params["main_b_mm"]) / 1000 * main_rib_height * float(params["secondary_beam_spacing_m"])
        + gamma_g
        * float(params["plaster_unit_weight"])
        * float(params["plaster_thickness_mm"])
        / 1000
        * main_rib_height
        * 2
        * float(params["secondary_beam_spacing_m"])
    )
    main_live_design = gamma_q * float(params["live_load"]) * float(params["main_beam_spacing_m"]) * float(params["secondary_beam_spacing_m"])

    return {
        "slab_dead_standard": slab_dead_standard,
        "slab_dead_design": slab_dead_design,
        "slab_live_design": slab_live_design,
        "slab_total_design": slab_dead_design + slab_live_design,
        "secondary_dead_standard": secondary_dead_standard,
        "secondary_dead_design": secondary_dead_design,
        "secondary_live_design": secondary_live_design,
        "secondary_total_design": secondary_dead_design + secondary_live_design,
        "main_dead_corrected": main_dead_corrected,
        "main_dead_original": float(params.get("course_main_original_dead_design_kN", 54.77913)),
        "main_live_design": main_live_design,
    }


def _benchmark_line_force_rows(
    member: str,
    total_design_load: float,
    benchmarks: list[dict],
    load_unit: str,
) -> pd.DataFrame:
    """用小组表基准值反算综合系数，并随当前荷载按同一口径缩放。"""
    rows: list[dict] = []
    for item in benchmarks:
        span = float(item["span_m"])
        if "moment_ref" in item:
            coeff = float(item["moment_ref"]) / (float(item["default_total_load"]) * span**2)
            value = coeff * total_design_load * span**2
            rows.append(
                {
                    "构件": member,
                    "截面": item["section"],
                    "内力类型": "M",
                    "计算跨度/净跨": span,
                    "综合系数": _round(coeff, 6),
                    "荷载": _round(total_design_load, 5),
                    "荷载单位": load_unit,
                    "内力值": _round(value, 5),
                    "单位": "kN·m",
                    "小组表基准值": item["moment_ref"],
                    "说明": item.get("note", "按小组表综合系数法缩放"),
                }
            )
        if "shear_ref" in item:
            coeff = float(item["shear_ref"]) / (float(item["default_total_load"]) * span)
            value = coeff * total_design_load * span
            rows.append(
                {
                    "构件": member,
                    "截面": item["section"],
                    "内力类型": "V",
                    "计算跨度/净跨": span,
                    "综合系数": _round(coeff, 6),
                    "荷载": _round(total_design_load, 5),
                    "荷载单位": load_unit,
                    "内力值": _round(value, 5),
                    "单位": "kN",
                    "小组表基准值": item["shear_ref"],
                    "说明": item.get("note", "按小组表综合系数法缩放"),
                }
            )
    return pd.DataFrame(rows)


def _main_load_cases(params: dict, loads: dict[str, float]) -> pd.DataFrame:
    adopted = str(params.get("course_main_load_case", SCREENSHOT_LOAD_CASE))
    return pd.DataFrame(
        [
            {
                "口径": CORRECTED_LOAD_CASE,
                "是否采用": "是" if adopted == CORRECTED_LOAD_CASE else "否",
                "Gd (kN/点)": _round(loads["main_dead_corrected"], 5),
                "Qd (kN/点)": _round(loads["main_live_design"], 5),
                "来源": "按当前 300×600、h0≈560、次梁 g=7.53186 kN/m 口径重算",
                "复核标记": "推荐用于300×600最终统一计算；与补充截图内力不完全一致，需复核",
            },
            {
                "口径": SCREENSHOT_LOAD_CASE,
                "是否采用": "是" if adopted != CORRECTED_LOAD_CASE else "否",
                "Gd (kN/点)": _round(loads["main_dead_original"], 5),
                "Qd (kN/点)": _round(loads["main_live_design"], 5),
                "来源": "小组新表/截图原始恒载设计值",
                "复核标记": "用于复现补充页 M/V/As；与300×600修正恒载存在口径冲突，需复核",
            },
        ]
    )


def _main_forces(params: dict, loads: dict[str, float]) -> pd.DataFrame:
    adopted = str(params.get("course_main_load_case", SCREENSHOT_LOAD_CASE))
    gd = loads["main_dead_corrected"] if adopted == CORRECTED_LOAD_CASE else loads["main_dead_original"]
    qd = loads["main_live_design"]
    rows: list[dict] = []
    moment_specs = [
        ("边跨跨中 1", 5.8905, 0.244, 0.289, "M1"),
        ("B支座中心", 6.0, -0.267, -0.311, "B支座中心M"),
        ("中跨跨中 2", 6.0, 0.067, 0.200, "M2"),
    ]
    for section, span, kg, kq, label in moment_specs:
        value = (kg * gd + kq * qd) * span
        rows.append(
            {
                "采用口径": adopted,
                "计算截面": section,
                "项目": label,
                "l0/ln (m)": span,
                "恒载系数": kg,
                "活载系数": kq,
                "Gd (kN/点)": _round(gd, 5),
                "Qd (kN/点)": _round(qd, 5),
                "内力值": _round(value, 5),
                "单位": "kN·m",
                "说明": "M=(kmG·Gd+kmQ·Qd)·l0",
            }
        )

    center_m = next(row["内力值"] for row in rows if row["计算截面"] == "B支座中心")
    edge_m = 165.74025 * (abs(center_m) / 195.2377662)
    rows.append(
        {
            "采用口径": adopted,
            "计算截面": "B支座边缘",
            "项目": "M'",
            "l0/ln (m)": 6.0,
            "恒载系数": "",
            "活载系数": "",
            "Gd (kN/点)": _round(gd, 5),
            "Qd (kN/点)": _round(qd, 5),
            "内力值": _round(abs(edge_m), 5),
            "单位": "kN·m",
            "说明": "按补充页支座边缘弯矩与中心弯矩比例换算；边缘公式来源需复核",
        }
    )

    shear_specs = [
        ("A支座", 5.610, 0.733, 0.866, "VA"),
        ("B左", 5.850, -1.267, -1.311, "VB左"),
        ("B右", 5.850, 1.000, 1.222, "VB右"),
    ]
    for section, span, kg, kq, label in shear_specs:
        value = kg * gd + kq * qd
        note = "V=kvG·Gd+kvQ·Qd"
        if section == "B左":
            note += "；补充表系数栏写 kv2=-1.110，但剪力值对应约 -1.311，标记需复核"
        rows.append(
            {
                "采用口径": adopted,
                "计算截面": section,
                "项目": label,
                "l0/ln (m)": span,
                "恒载系数": kg,
                "活载系数": kq,
                "Gd (kN/点)": _round(gd, 5),
                "Qd (kN/点)": _round(qd, 5),
                "内力值": _round(value, 5),
                "单位": "kN",
                "说明": note,
            }
        )
    return pd.DataFrame(rows)


def _design_rebar_rows(params: dict, slab_df: pd.DataFrame, secondary_df: pd.DataFrame, main_df: pd.DataFrame) -> pd.DataFrame:
    gamma_d = float(params.get("design_internal_force_factor", 1.2))
    fc = float(params["fc"])
    rows: list[dict] = []

    def add(member: str, section: str, moment: float, b_mm: float, h0_mm: float, fy: float, section_type: str, note: str) -> None:
        design_moment = abs(moment) * gamma_d
        area, x_mm = calculate_required_as(design_moment, fc, fy, b_mm, h0_mm)
        rows.append(
            {
                "构件": member,
                "截面": section,
                "计算用内力": _round(moment, 5),
                "γd": gamma_d,
                "γdM": _round(design_moment, 5),
                "b或bf' (mm)": b_mm,
                "h0 (mm)": h0_mm,
                "fy (N/mm2)": fy,
                "计算 As (mm2)": _round(area, 3),
                "x (mm)": _round(x_mm, 3),
                "截面类型": section_type,
                "说明": note,
            }
        )

    slab_values = {row["截面"]: float(row["内力值"]) for _, row in slab_df[slab_df["内力类型"] == "M"].iterrows()}
    add("板", "边跨跨中 1", slab_values["边跨跨中 1"], 1000.0, float(params["slab_h0_mm"]), float(params["fy_slab"]), "矩形板带", "与小组表边跨跨中 As 对账")
    add("板", "B支座边缘", 2.504, 1000.0, float(params["slab_h0_mm"]), float(params["fy_slab"]), "矩形板带", "小组表板支座 As 采用边缘 M'，非支座中心负弯矩")
    add("板", "中跨跨中 2", slab_values["中跨跨中 2"], 1000.0, float(params["slab_h0_mm"]), float(params["fy_slab"]), "矩形板带", "与小组表中跨跨中 As 对账")

    secondary_values = {row["截面"]: float(row["内力值"]) for _, row in secondary_df[secondary_df["内力类型"] == "M"].iterrows()}
    secondary_bf = 1666.7
    add("次梁", "边跨跨中 1", secondary_values["边跨跨中 1"], secondary_bf, float(params["secondary_h0_mm"]), float(params["fy_beam"]), "第一类T形截面", "与小组表次梁边跨 As 对账")
    add("次梁", "B支座中心", secondary_values["B支座"], float(params["secondary_b_mm"]), float(params["secondary_h0_mm"]), float(params["fy_beam"]), "矩形截面", "小组表次梁支座 As 采用支座中心负弯矩")
    add("次梁", "中跨跨中 2", secondary_values["中跨跨中 2"], secondary_bf, float(params["secondary_h0_mm"]), float(params["fy_beam"]), "第一类T形截面", "与小组表次梁中跨 As 对账")

    main_values = {row["计算截面"]: float(row["内力值"]) for _, row in main_df[main_df["单位"] == "kN·m"].iterrows()}
    main_bf = float(params.get("main_flange_width_mm") or 2000.0)
    add("主梁", "边跨跨中 1", main_values["边跨跨中 1"], main_bf, float(params["main_h0_mm"]), float(params["fy_beam"]), "第一类T形截面", "γd 后应接近 1283.03 mm2")
    add("主梁", "B支座边缘", main_values["B支座边缘"], float(params["main_b_mm"]), float(params["main_h0_mm"]), float(params["fy_beam"]), "矩形截面", "小组表主梁 B 支座 As 采用边缘 M'，非中心 M")
    add("主梁", "中跨跨中 2", main_values["中跨跨中 2"], main_bf, float(params["main_h0_mm"]), float(params["fy_beam"]), "第一类T形截面", "γd 后应接近 659.46 mm2")

    return pd.DataFrame(rows)


def calculate_course_design_method(params: dict) -> CourseDesignResult:
    """按小组表口径生成课程设计系数法对照结果。"""
    loads = _line_loads(params)

    slab_df = _benchmark_line_force_rows(
        "板",
        loads["slab_total_design"],
        [
            {"section": "边跨跨中 1", "span_m": 1.958, "moment_ref": 2.552, "shear_ref": 5.732, "default_total_load": 7.85025},
            {"section": "B支座", "span_m": 1.98, "moment_ref": -3.289, "shear_ref": -8.527, "default_total_load": 7.85025, "note": "支座中心负弯矩；小组表另列边缘 M'=2.504"},
            {"section": "中跨跨中 2", "span_m": 1.98, "moment_ref": 1.448, "shear_ref": 7.743, "default_total_load": 7.85025},
            {"section": "C支座", "span_m": 1.98, "moment_ref": -2.732, "shear_ref": -7.138, "default_total_load": 7.85025, "note": "小组表主梁同类截面未完整列出，需复核"},
        ],
        "kN/m",
    )
    secondary_df = _benchmark_line_force_rows(
        "次梁",
        loads["secondary_total_design"],
        [
            {"section": "边跨跨中 1", "span_m": 4.8405, "moment_ref": 35.044, "shear_ref": 32.876, "default_total_load": 17.13186},
            {"section": "B支座", "span_m": 4.935, "moment_ref": -39.840, "shear_ref": -49.269, "default_total_load": 17.13186, "note": "小组表次梁支座配筋采用支座中心负弯矩"},
            {"section": "中跨跨中 2", "span_m": 4.935, "moment_ref": 21.806, "shear_ref": 44.790, "default_total_load": 17.13186},
            {"section": "C支座", "span_m": 4.935, "moment_ref": -32.148, "shear_ref": -41.618, "default_total_load": 17.13186},
        ],
        "kN/m",
    )
    load_cases_df = _main_load_cases(params, loads)
    main_df = _main_forces(params, loads)
    rebar_df = _design_rebar_rows(params, slab_df, secondary_df, main_df)
    review_df = pd.DataFrame(
        [
            {
                "项目": "主梁恒载口径",
                "结论": "需复核",
                "说明": "300×600 修正口径 Gd≈53.938 kN/点；补充页 M/V 复现需要截图原始 Gd≈54.77913 kN/点。",
            },
            {
                "项目": "主梁 B左剪力系数",
                "结论": "需复核",
                "说明": "补充页系数栏 kv2=-1.110 不能得到 V=-144.919 kN；数值反推约为 -1.311。",
            },
            {
                "项目": "支座配筋取值位置",
                "结论": "需复核",
                "说明": "板与主梁支座 As 使用支座边缘 M' 更接近小组表；次梁支座 As 使用支座中心负弯矩。",
            },
        ]
    )
    return CourseDesignResult(slab_df, secondary_df, load_cases_df, main_df, rebar_df, review_df)
