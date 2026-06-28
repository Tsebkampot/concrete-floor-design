"""公共默认参数和表格工具。

本文件集中保存课程设计辅助计算所需的默认值。界面会把这些参数写入
``st.session_state``，板、次梁、主梁和导出模块共用同一套数据，避免
不同页面重复输入造成单位或数值不一致。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


CONCRETE_DESIGN_STRENGTH = {
    "C20": 9.6,
    "C25": 11.9,
    "C30": 14.3,
}

STEEL_DESIGN_STRENGTH = {
    "I 级": 210.0,
    "II 级": 300.0,
    "III 级": 360.0,
}


@dataclass
class DesignParameters:
    """整体式单向板肋形楼盖统一输入参数。"""

    l1_m: float = 18.0
    l2_m: float = 30.0
    main_beam_spacing_m: float = 6.0
    secondary_beam_spacing_m: float = 2.0
    strip_width_m: float = 1.0
    wall_thickness_mm: float = 370.0
    slab_bearing_length_mm: float = 120.0
    secondary_bearing_length_mm: float = 240.0
    main_bearing_length_mm: float = 240.0
    column_b_mm: float = 350.0
    column_h_mm: float = 350.0
    concrete_grade: str = "C20"
    slab_steel_grade: str = "I 级"
    stirrup_steel_grade: str = "I 级"
    beam_steel_grade: str = "II 级"
    fc: float = 9.6
    fy_slab: float = 210.0
    fy_beam: float = 300.0
    fyv: float = 210.0
    concrete_unit_weight: float = 25.0
    terrazzo_load: float = 0.65
    plaster_thickness_mm: float = 15.0
    plaster_unit_weight: float = 17.0
    live_load: float = 4.0
    gamma_g: float = 1.05
    gamma_q: float = 1.2
    importance_factor: float = 1.0
    slab_h_mm: float = 80.0
    slab_h0_mm: float = 60.0
    secondary_b_mm: float = 200.0
    secondary_h_mm: float = 400.0
    secondary_h0_mm: float = 360.0
    main_b_mm: float = 300.0
    main_h_mm: float = 650.0
    main_h0_mm: float = 600.0
    secondary_flange_width_mm: float = 0.0
    main_flange_width_mm: float = 0.0
    slab_span_m: float = 2.0
    secondary_span_m: float = 6.0
    main_span_m: float = 6.0
    slab_spans_text: str = "2,2,2"
    secondary_spans_text: str = "6,6,6,6,6"
    main_spans_text: str = "6,6,6"
    slab_supports_text: str = "pin,pin,pin,pin"
    secondary_supports_text: str = "pin,pin,pin,pin,pin,pin"
    main_supports_text: str = "pin,pin,pin,pin"
    slab_live_spans_text: str = "1,2,3"
    secondary_live_spans_text: str = "1,2,3,4,5"
    main_live_spans_text: str = "1,2,3"
    main_point_positions_text: str = ""
    secondary_to_main_support_number: int = 3
    elastic_modulus_mpa: float = 25500.0
    slab_stiffness_factor: float = 1.0
    secondary_stiffness_factor: float = 1.0
    main_stiffness_factor: float = 1.0
    automatic_live_patterns: bool = True

    def to_dict(self) -> dict[str, float | str]:
        """返回可用于表格和导出的普通字典。"""
        return asdict(self)


def default_parameters() -> DesignParameters:
    """生成一份默认参数。"""
    return DesignParameters()


def round_value(value: float, digits: int = 4) -> float:
    """统一数值显示精度。"""
    return round(float(value), digits)
