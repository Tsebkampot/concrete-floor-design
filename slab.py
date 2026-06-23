"""整体式单向板肋形楼盖的板计算模块。"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from calculations.rebar import RebarOption, check_rebar_options


@dataclass(frozen=True)
class SlabInput:
    """单向板计算输入参数。"""

    h_mm: float = 80
    concrete_unit_weight: float = 25
    terrazzo_load: float = 0.65
    plaster_thickness_mm: float = 15
    plaster_unit_weight: float = 17
    live_load: float = 4
    gamma_g: float = 1.05
    gamma_q: float = 1.2
    strip_width_m: float = 1
    l0_m: float = 2.0
    alpha: float = 1 / 11
    fc: float = 9.6
    fy: float = 300
    h0_mm: float = 60
    section_name: str = "跨中"


@dataclass(frozen=True)
class SlabResult:
    """单向板计算输出结果。"""

    input: SlabInput
    self_weight_kN_m2: float
    plaster_load_kN_m2: float
    dead_load_standard_kN_m2: float
    dead_load_design_kN_m2: float
    live_load_design_kN_m2: float
    line_load_design_kN_m: float
    moment_kN_m: float
    moment_abs_kN_m: float
    required_as_mm2_per_m: float
    compression_zone_x_mm: float
    rebar_options: list[RebarOption]


def validate_slab_input(data: SlabInput) -> None:
    """检查输入参数是否合法。"""
    positive_fields = {
        "板厚 h": data.h_mm,
        "混凝土重度": data.concrete_unit_weight,
        "抹面重度": data.plaster_unit_weight,
        "恒载分项系数": data.gamma_g,
        "活载分项系数": data.gamma_q,
        "板带宽度": data.strip_width_m,
        "计算跨度 l0": data.l0_m,
        "混凝土抗压强度设计值 fc": data.fc,
        "钢筋抗拉强度设计值 fy": data.fy,
        "截面有效高度 h0": data.h0_mm,
    }
    for name, value in positive_fields.items():
        if value <= 0:
            raise ValueError(f"{name}必须大于 0")

    non_negative_fields = {
        "水磨石面层荷载": data.terrazzo_load,
        "抹面厚度": data.plaster_thickness_mm,
        "楼面活荷载": data.live_load,
    }
    for name, value in non_negative_fields.items():
        if value < 0:
            raise ValueError(f"{name}不能为负数")

    if data.alpha == 0:
        raise ValueError("弯矩系数 alpha 不能为 0")
    if data.h0_mm >= data.h_mm:
        raise ValueError("截面有效高度 h0 应小于板厚 h")


def calculate_loads(data: SlabInput) -> dict[str, float]:
    """
    计算荷载标准值和设计值。

    单位换算：
    - 板厚 mm 转 m：h_mm / 1000
    - 抹面厚度 mm 转 m：plaster_thickness_mm / 1000
    - 面荷载 kN/m2 转线荷载 kN/m：面荷载乘以板带宽度 m
    """
    validate_slab_input(data)

    self_weight = data.h_mm / 1000 * data.concrete_unit_weight
    plaster_load = data.plaster_thickness_mm / 1000 * data.plaster_unit_weight
    dead_standard = self_weight + data.terrazzo_load + plaster_load
    dead_design = data.gamma_g * dead_standard
    live_design = data.gamma_q * data.live_load
    line_design = (dead_design + live_design) * data.strip_width_m

    return {
        "self_weight_kN_m2": self_weight,
        "plaster_load_kN_m2": plaster_load,
        "dead_load_standard_kN_m2": dead_standard,
        "dead_load_design_kN_m2": dead_design,
        "live_load_design_kN_m2": live_design,
        "line_load_design_kN_m": line_design,
    }


def calculate_moment(alpha: float, q_kN_m: float, l0_m: float) -> float:
    """
    计算控制截面弯矩。

    M = alpha * q * l0^2
    q 单位为 kN/m，l0 单位为 m，因此 M 单位为 kN·m。
    """
    if q_kN_m <= 0:
        raise ValueError("线荷载设计值必须大于 0")
    if l0_m <= 0:
        raise ValueError("计算跨度 l0 必须大于 0")
    if alpha == 0:
        raise ValueError("弯矩系数 alpha 不能为 0")
    return alpha * q_kN_m * l0_m**2


def calculate_required_as(
    moment_kN_m: float,
    fc: float,
    fy: float,
    b_mm: float,
    h0_mm: float,
) -> tuple[float, float]:
    """
    按单筋矩形截面简化公式计算所需受拉钢筋面积。

    采用 1 m 板带作为计算宽度：
    - b = strip_width_m * 1000，单位 mm
    - M 的单位换算：1 kN·m = 10^6 N·mm

    基本关系：
    - M = fc * b * x * (h0 - x / 2)
    - As = fc * b * x / fy

    这里取弯矩绝对值计算钢筋面积，正负号只表示受拉钢筋位置不同。
    """
    if fc <= 0 or fy <= 0 or b_mm <= 0 or h0_mm <= 0:
        raise ValueError("fc、fy、b、h0 均必须大于 0")

    moment_n_mm = abs(moment_kN_m) * 1_000_000
    discriminant = h0_mm**2 - 2 * moment_n_mm / (fc * b_mm)
    if discriminant < 0:
        raise ValueError("弯矩过大，按当前截面尺寸和材料强度无法用简化公式求解")

    compression_zone_x = h0_mm - math.sqrt(discriminant)
    required_as = fc * b_mm * compression_zone_x / fy
    return required_as, compression_zone_x


def calculate_slab(data: SlabInput) -> SlabResult:
    """完成单向板从荷载、弯矩到配筋的完整计算。"""
    validate_slab_input(data)
    loads = calculate_loads(data)
    moment = calculate_moment(data.alpha, loads["line_load_design_kN_m"], data.l0_m)
    b_mm = data.strip_width_m * 1000
    required_as, x_mm = calculate_required_as(moment, data.fc, data.fy, b_mm, data.h0_mm)
    options = check_rebar_options(required_as)

    return SlabResult(
        input=data,
        self_weight_kN_m2=loads["self_weight_kN_m2"],
        plaster_load_kN_m2=loads["plaster_load_kN_m2"],
        dead_load_standard_kN_m2=loads["dead_load_standard_kN_m2"],
        dead_load_design_kN_m2=loads["dead_load_design_kN_m2"],
        live_load_design_kN_m2=loads["live_load_design_kN_m2"],
        line_load_design_kN_m=loads["line_load_design_kN_m"],
        moment_kN_m=moment,
        moment_abs_kN_m=abs(moment),
        required_as_mm2_per_m=required_as,
        compression_zone_x_mm=x_mm,
        rebar_options=options,
    )


def result_to_dict(result: SlabResult) -> dict:
    """把 dataclass 结果转成普通字典，便于导出。"""
    data = asdict(result)
    data["rebar_options"] = [asdict(option) for option in result.rebar_options]
    return data
