"""整体式单向板肋形楼盖的主梁计算模块。"""

from __future__ import annotations

from dataclasses import dataclass

from calculations.secondary_beam import (
    LongitudinalRebarOption,
    StirrupOption,
    check_longitudinal_options,
    check_stirrup_options,
    estimate_stirrups,
)
from calculations.slab import calculate_required_as


@dataclass(frozen=True)
class MainBeamInput:
    """主梁计算输入参数。"""

    secondary_dead_load_kN_m: float = 7.583
    secondary_span_m: float = 6.0
    secondary_spacing_m: float = 2.0
    b_mm: float = 300
    h_mm: float = 650
    hf_mm: float = 80
    concrete_unit_weight: float = 25
    plaster_thickness_mm: float = 15
    plaster_unit_weight: float = 17
    live_load_kN_m2: float = 4
    gamma_g: float = 1.05
    gamma_q: float = 1.2
    l0_m: float = 6.0
    alpha: float = 0.25
    beta: float = 0.5
    fc: float = 9.6
    fy: float = 300
    fyv: float = 270
    h0_mm: float = 600
    section_name: str = "跨中"


@dataclass(frozen=True)
class MainBeamResult:
    """主梁计算输出结果。"""

    input: MainBeamInput
    secondary_dead_concentrated_kN: float
    beam_self_weight_kN: float
    beam_plaster_load_kN: float
    dead_load_standard_kN: float
    dead_load_design_kN: float
    live_load_standard_kN: float
    live_load_design_kN: float
    total_concentrated_design_kN: float
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
    return "主梁模块已实现"


def validate_main_beam_input(data: MainBeamInput) -> None:
    """检查主梁输入参数是否合法。"""
    positive_fields = {
        "次梁传来的恒载标准值": data.secondary_dead_load_kN_m,
        "次梁跨度": data.secondary_span_m,
        "次梁间距": data.secondary_spacing_m,
        "主梁宽度 b": data.b_mm,
        "主梁高度 h": data.h_mm,
        "板厚 hf": data.hf_mm,
        "混凝土重度": data.concrete_unit_weight,
        "粉刷重度": data.plaster_unit_weight,
        "恒载分项系数": data.gamma_g,
        "活载分项系数": data.gamma_q,
        "主梁计算跨度 l0": data.l0_m,
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
        "活荷载标准值": data.live_load_kN_m2,
    }
    for name, value in non_negative_fields.items():
        if value < 0:
            raise ValueError(f"{name}不能为负数")

    if data.alpha == 0:
        raise ValueError("弯矩系数 alpha 不能为 0")
    if data.beta == 0:
        raise ValueError("剪力系数 beta 不能为 0")
    if data.h_mm <= data.hf_mm:
        raise ValueError("主梁高度 h 应大于板厚 hf")
    if data.h0_mm >= data.h_mm:
        raise ValueError("截面有效高度 h0 应小于主梁高度 h")


def calculate_main_beam_loads(data: MainBeamInput) -> dict[str, float]:
    """
    计算主梁集中荷载基本值。

    单位换算：
    - mm 转 m：除以 1000
    - 次梁传来的线恒载 kN/m 乘以次梁跨度，得到作用在主梁上的集中力 kN
    - 主梁自重和粉刷按相邻次梁间距这一段长度折算成集中荷载
    """
    validate_main_beam_input(data)

    rib_height_m = (data.h_mm - data.hf_mm) / 1000
    beam_width_m = data.b_mm / 1000
    plaster_thickness_m = data.plaster_thickness_mm / 1000

    secondary_dead_concentrated = data.secondary_dead_load_kN_m * data.secondary_span_m
    beam_self_weight = (
        data.concrete_unit_weight
        * beam_width_m
        * rib_height_m
        * data.secondary_spacing_m
    )
    beam_plaster_load = (
        data.plaster_unit_weight
        * plaster_thickness_m
        * rib_height_m
        * 2
        * data.secondary_spacing_m
    )
    dead_standard = secondary_dead_concentrated + beam_self_weight + beam_plaster_load
    dead_design = data.gamma_g * dead_standard
    live_standard = data.live_load_kN_m2 * data.secondary_span_m * data.secondary_spacing_m
    live_design = data.gamma_q * live_standard
    total_design = dead_design + live_design

    return {
        "secondary_dead_concentrated_kN": secondary_dead_concentrated,
        "beam_self_weight_kN": beam_self_weight,
        "beam_plaster_load_kN": beam_plaster_load,
        "dead_load_standard_kN": dead_standard,
        "dead_load_design_kN": dead_design,
        "live_load_standard_kN": live_standard,
        "live_load_design_kN": live_design,
        "total_concentrated_design_kN": total_design,
    }


def calculate_point_moment(alpha: float, p_kN: float, l0_m: float) -> float:
    """
    计算主梁控制截面弯矩。

    课程设计基本版按集中荷载系数计算：
    M = alpha * P * l0
    P 单位为 kN，l0 单位为 m，因此 M 单位为 kN·m。
    """
    if alpha == 0:
        raise ValueError("弯矩系数 alpha 不能为 0")
    if p_kN <= 0:
        raise ValueError("总集中荷载设计值必须大于 0")
    if l0_m <= 0:
        raise ValueError("主梁计算跨度 l0 必须大于 0")
    return alpha * p_kN * l0_m


def calculate_point_shear(beta: float, p_kN: float) -> float:
    """
    计算主梁控制截面剪力。

    课程设计基本版按集中荷载系数计算：
    V = beta * P
    """
    if beta == 0:
        raise ValueError("剪力系数 beta 不能为 0")
    if p_kN <= 0:
        raise ValueError("总集中荷载设计值必须大于 0")
    return beta * p_kN


def calculate_main_beam(data: MainBeamInput) -> MainBeamResult:
    """完成主梁从荷载、内力到纵筋和箍筋的完整计算。"""
    validate_main_beam_input(data)
    loads = calculate_main_beam_loads(data)
    moment = calculate_point_moment(
        data.alpha,
        loads["total_concentrated_design_kN"],
        data.l0_m,
    )
    shear = calculate_point_shear(data.beta, loads["total_concentrated_design_kN"])
    required_as, x_mm = calculate_required_as(moment, data.fc, data.fy, data.b_mm, data.h0_mm)
    vc_kN, required_av_over_s = estimate_stirrups(
        shear,
        data.fc,
        data.b_mm,
        data.h0_mm,
        data.fyv,
    )

    return MainBeamResult(
        input=data,
        secondary_dead_concentrated_kN=loads["secondary_dead_concentrated_kN"],
        beam_self_weight_kN=loads["beam_self_weight_kN"],
        beam_plaster_load_kN=loads["beam_plaster_load_kN"],
        dead_load_standard_kN=loads["dead_load_standard_kN"],
        dead_load_design_kN=loads["dead_load_design_kN"],
        live_load_standard_kN=loads["live_load_standard_kN"],
        live_load_design_kN=loads["live_load_design_kN"],
        total_concentrated_design_kN=loads["total_concentrated_design_kN"],
        moment_kN_m=moment,
        moment_abs_kN_m=abs(moment),
        shear_kN=shear,
        shear_abs_kN=abs(shear),
        required_as_mm2=required_as,
        compression_zone_x_mm=x_mm,
        concrete_shear_capacity_kN=vc_kN,
        required_av_over_s_mm2_per_mm=required_av_over_s,
        longitudinal_options=check_longitudinal_options(
            required_as,
            options=[(2, 20), (3, 20), (4, 18), (4, 20), (4, 22), (5, 22)],
        ),
        stirrup_options=check_stirrup_options(required_av_over_s),
    )
