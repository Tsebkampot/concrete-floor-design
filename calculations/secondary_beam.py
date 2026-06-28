"""整体式单向板肋形楼盖的次梁计算模块。"""

from __future__ import annotations

import math
from dataclasses import dataclass

from calculations.rebar import bar_area, recommend_longitudinal_rebar, recommend_stirrups
from calculations.slab import calculate_required_as
from calculations.matrix_stiffness import BeamElement, BeamNode, elastic_flexural_rigidity_kN_m2, solve_continuous_beam


@dataclass(frozen=True)
class LongitudinalRebarOption:
    """次梁纵向受力钢筋方案。"""

    name: str
    count: int
    diameter_mm: float
    area_mm2: float
    is_ok: bool
    over_ratio_percent: float = 0.0
    evaluation: str = "不足"


@dataclass(frozen=True)
class StirrupOption:
    """次梁箍筋方案。"""

    name: str
    diameter_mm: float
    legs: int
    spacing_mm: float
    av_over_s_mm2_per_mm: float
    is_ok: bool
    evaluation: str = "需人工按教材/规范复核"


@dataclass(frozen=True)
class SecondaryBeamInput:
    """次梁计算输入参数。"""

    slab_dead_load_kN_m2: float = 2.91
    tributary_width_m: float = 2.0
    b_mm: float = 200
    h_mm: float = 400
    hf_mm: float = 80
    concrete_unit_weight: float = 25
    plaster_thickness_mm: float = 15
    plaster_unit_weight: float = 17
    live_load_kN_m2: float = 4
    gamma_g: float = 1.05
    gamma_q: float = 1.2
    l0_m: float = 4.5
    alpha: float = 1 / 11
    beta: float = 0.5
    fc: float = 9.6
    fy: float = 300
    fyv: float = 270
    h0_mm: float = 360
    section_name: str = "跨中"
    elastic_modulus_mpa: float = 25500
    stiffness_factor: float = 1.0


@dataclass(frozen=True)
class SecondaryBeamResult:
    """次梁计算输出结果。"""

    input: SecondaryBeamInput
    slab_dead_line_load_kN_m: float
    beam_self_weight_kN_m: float
    beam_plaster_load_kN_m: float
    dead_load_standard_kN_m: float
    dead_load_design_kN_m: float
    live_load_standard_kN_m: float
    live_load_design_kN_m: float
    total_line_load_design_kN_m: float
    moment_kN_m: float
    moment_abs_kN_m: float
    shear_kN: float
    shear_abs_kN: float
    required_as_mm2: float
    compression_zone_x_mm: float
    concrete_shear_capacity_kN: float
    required_av_over_s_mm2_per_mm: float
    longitudinal_options: list[LongitudinalRebarOption]
    stirrup_options: list[StirrupOption]


def module_status() -> str:
    """返回模块当前状态，便于界面展示。"""
    return "次梁模块已实现"


def validate_secondary_beam_input(data: SecondaryBeamInput) -> None:
    """检查次梁输入参数是否合法。"""
    positive_fields = {
        "板传来的恒载标准值": data.slab_dead_load_kN_m2,
        "次梁间距": data.tributary_width_m,
        "次梁宽度 b": data.b_mm,
        "次梁高度 h": data.h_mm,
        "板厚 hf": data.hf_mm,
        "混凝土重度": data.concrete_unit_weight,
        "粉刷重度": data.plaster_unit_weight,
        "恒载分项系数": data.gamma_g,
        "活载分项系数": data.gamma_q,
        "次梁计算跨度 l0": data.l0_m,
        "混凝土强度设计值 fc": data.fc,
        "钢筋强度设计值 fy": data.fy,
        "箍筋强度设计值 fyv": data.fyv,
        "截面有效高度 h0": data.h0_mm,
    }
    for name, value in positive_fields.items():
        if value <= 0:
            raise ValueError(f"{name}必须大于 0")

    non_negative_fields = {
        "粉刷厚度": data.plaster_thickness_mm,
        "楼面活荷载标准值": data.live_load_kN_m2,
    }
    for name, value in non_negative_fields.items():
        if value < 0:
            raise ValueError(f"{name}不能为负数")

    if data.h_mm <= data.hf_mm:
        raise ValueError("次梁高度 h 应大于板厚 hf")
    if data.h0_mm >= data.h_mm:
        raise ValueError("截面有效高度 h0 应小于次梁高度 h")


def calculate_secondary_beam_loads(data: SecondaryBeamInput) -> dict[str, float]:
    """
    计算次梁线荷载。

    单位换算：
    - mm 转 m：除以 1000
    - 板面荷载 kN/m2 转次梁线荷载 kN/m：乘以次梁承担的板带宽度
    - 次梁自重只计算板下梁肋高度 h - hf，避免重复计入板自重
    """
    validate_secondary_beam_input(data)

    rib_height_m = (data.h_mm - data.hf_mm) / 1000
    beam_width_m = data.b_mm / 1000
    plaster_thickness_m = data.plaster_thickness_mm / 1000

    slab_dead_line = data.slab_dead_load_kN_m2 * data.tributary_width_m
    beam_self_weight = data.concrete_unit_weight * beam_width_m * rib_height_m
    beam_plaster_load = data.plaster_unit_weight * plaster_thickness_m * rib_height_m * 2
    dead_standard = slab_dead_line + beam_self_weight + beam_plaster_load
    dead_design = data.gamma_g * dead_standard
    live_standard = data.live_load_kN_m2 * data.tributary_width_m
    live_design = data.gamma_q * live_standard
    total_design = dead_design + live_design

    return {
        "slab_dead_line_load_kN_m": slab_dead_line,
        "beam_self_weight_kN_m": beam_self_weight,
        "beam_plaster_load_kN_m": beam_plaster_load,
        "dead_load_standard_kN_m": dead_standard,
        "dead_load_design_kN_m": dead_design,
        "live_load_standard_kN_m": live_standard,
        "live_load_design_kN_m": live_design,
        "total_line_load_design_kN_m": total_design,
    }


def calculate_shear(beta: float, q_kN_m: float, l0_m: float) -> float:
    """
    旧手算对比：按经验系数计算剪力，不参与正式设计链路。

    V = beta * q * l0
    q 单位为 kN/m，l0 单位为 m，因此 V 单位为 kN。
    """
    if beta == 0:
        raise ValueError("剪力系数 beta 不能为 0")
    if q_kN_m <= 0:
        raise ValueError("总线荷载设计值必须大于 0")
    if l0_m <= 0:
        raise ValueError("计算跨度 l0 必须大于 0")
    return beta * q_kN_m * l0_m


def estimate_stirrups(
    shear_kN: float,
    fc: float,
    b_mm: float,
    h0_mm: float,
    fyv: float,
) -> tuple[float, float]:
    """
    估算斜截面箍筋需求。

    课程设计辅助计算中采用简化估算：
    - 混凝土抗剪承载力 Vc = 0.7 * sqrt(fc) * b * h0
    - 需要箍筋承担的剪力 Vs = max(V - Vc, 0)
    - 箍筋面积间距比 Av/s = Vs / (fyv * h0)

    单位说明：
    - V 由 kN 换算为 N
    - fc、fyv 单位为 N/mm2
    - b、h0 单位为 mm
    - Av/s 单位为 mm2/mm
    """
    if fc <= 0 or b_mm <= 0 or h0_mm <= 0 or fyv <= 0:
        raise ValueError("fc、b、h0、fyv 均必须大于 0")

    shear_n = abs(shear_kN) * 1000
    concrete_capacity_n = 0.7 * math.sqrt(fc) * b_mm * h0_mm
    required_by_stirrups_n = max(shear_n - concrete_capacity_n, 0)
    required_av_over_s = required_by_stirrups_n / (fyv * h0_mm)
    return concrete_capacity_n / 1000, required_av_over_s


def check_longitudinal_options(
    required_as_mm2: float,
    options: list[tuple[int, int]] | None = None,
) -> list[LongitudinalRebarOption]:
    """判断常用次梁纵筋方案是否满足所需受拉钢筋面积。"""
    if required_as_mm2 < 0:
        raise ValueError("所需纵筋面积不能为负数")

    if options is None:
        options = [(2, 12), (2, 14), (2, 16), (3, 16), (2, 18), (3, 18), (2, 20), (3, 20), (2, 22)]
    return [
        LongitudinalRebarOption(
            name=item.name,
            count=item.count,
            diameter_mm=item.diameter_mm,
            area_mm2=item.area_mm2,
            is_ok=item.is_ok,
            over_ratio_percent=item.over_ratio_percent,
            evaluation=item.evaluation,
        )
        for item in recommend_longitudinal_rebar(required_as_mm2, options)
    ]


def check_stirrup_options(required_av_over_s: float) -> list[StirrupOption]:
    """判断常用双肢箍方案是否满足 Av/s 要求。"""
    if required_av_over_s < 0:
        raise ValueError("所需箍筋面积间距比不能为负数")

    return [
        StirrupOption(
            name=item.name,
            diameter_mm=item.diameter_mm,
            legs=item.legs,
            spacing_mm=item.spacing_mm,
            av_over_s_mm2_per_mm=item.av_over_s_mm2_per_mm,
            is_ok=item.is_ok,
            evaluation=item.evaluation,
        )
        for item in recommend_stirrups(required_av_over_s)
    ]


def calculate_secondary_beam(data: SecondaryBeamInput) -> SecondaryBeamResult:
    """完成次梁基础计算；内力由统一矩阵刚度求解器获得。"""
    validate_secondary_beam_input(data)
    loads = calculate_secondary_beam_loads(data)
    ei = elastic_flexural_rigidity_kN_m2(data.elastic_modulus_mpa, data.b_mm, data.h_mm, data.stiffness_factor)
    analysis = solve_continuous_beam(
        [BeamNode(0, 0.0, True), BeamNode(1, data.l0_m, True)],
        [BeamElement(0, 0, 1, ei, loads["total_line_load_design_kN_m"])],
    )
    moment = analysis.force_at(data.l0_m / 2).moment_kN_m
    shear = analysis.force_at(0.0, "right").shear_kN
    required_as, x_mm = calculate_required_as(moment, data.fc, data.fy, data.b_mm, data.h0_mm)
    vc_kN, required_av_over_s = estimate_stirrups(
        shear,
        data.fc,
        data.b_mm,
        data.h0_mm,
        data.fyv,
    )

    return SecondaryBeamResult(
        input=data,
        slab_dead_line_load_kN_m=loads["slab_dead_line_load_kN_m"],
        beam_self_weight_kN_m=loads["beam_self_weight_kN_m"],
        beam_plaster_load_kN_m=loads["beam_plaster_load_kN_m"],
        dead_load_standard_kN_m=loads["dead_load_standard_kN_m"],
        dead_load_design_kN_m=loads["dead_load_design_kN_m"],
        live_load_standard_kN_m=loads["live_load_standard_kN_m"],
        live_load_design_kN_m=loads["live_load_design_kN_m"],
        total_line_load_design_kN_m=loads["total_line_load_design_kN_m"],
        moment_kN_m=moment,
        moment_abs_kN_m=abs(moment),
        shear_kN=shear,
        shear_abs_kN=abs(shear),
        required_as_mm2=required_as,
        compression_zone_x_mm=x_mm,
        concrete_shear_capacity_kN=vc_kN,
        required_av_over_s_mm2_per_mm=required_av_over_s,
        longitudinal_options=check_longitudinal_options(required_as),
        stirrup_options=check_stirrup_options(required_av_over_s),
    )
