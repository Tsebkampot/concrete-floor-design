"""基于控制截面内力包络的逐截面配筋设计。"""

from __future__ import annotations

import math

import pandas as pd

from calculations.force_envelope import MemberEnvelopeResult
from calculations.secondary_beam import estimate_stirrups
from calculations.slab import calculate_required_as
from calculations.specification_parameters import COURSE_SPEC
from calculations.rebar import longitudinal_bars_fit


def _slab_option(required_as: float) -> tuple[str, float, float]:
    candidates = []
    for diameter in (6, 8, 10, 12, 14):
        area = math.pi * diameter**2 / 4
        for spacing in range(70, 251, 10):
            provided = area * 1000 / spacing
            if provided + 1e-9 >= required_as:
                candidates.append((provided - required_as, -spacing, f"Φ{diameter}@{spacing}", provided))
    if not candidates:
        return "常用方案不足，需人工加大钢筋", 0.0, 0.0
    _, _, name, provided = min(candidates)
    over = (provided - required_as) / required_as * 100 if required_as > 1e-9 else 0.0
    return name, provided, over


def _beam_option(required_as: float, b_mm: float, cover_mm: float | None = None) -> tuple[str, float, float, bool]:
    cover_mm = COURSE_SPEC.beam_cover_mm if cover_mm is None else cover_mm
    candidates = []
    for diameter in (12, 14, 16, 18, 20, 22, 25, 28, 32):
        area = math.pi * diameter**2 / 4
        clear_width = b_mm - 2 * (cover_mm + COURSE_SPEC.stirrup_diameter_mm)
        clear_spacing = max(COURSE_SPEC.min_clear_bar_spacing_mm, float(diameter))
        per_layer = int((clear_width + clear_spacing) // (diameter + clear_spacing)) if clear_width >= diameter else 0
        if per_layer <= 0:
            continue
        for count in range(2, 11):
            provided = count * area
            fits = longitudinal_bars_fit(b_mm, count, diameter, cover_mm=cover_mm)
            if provided + 1e-9 >= required_as and fits:
                layers = f"{count}Φ{diameter}" if count <= per_layer else f"{per_layer}+{count - per_layer}Φ{diameter}（两层）"
                candidates.append((provided - required_as, count, diameter, layers, provided))
    if not candidates:
        return "常用单/双层方案不足，需人工调整截面", 0.0, 0.0, False
    _, _, _, name, provided = min(candidates)
    over = (provided - required_as) / required_as * 100 if required_as > 1e-9 else 0.0
    return name, provided, over, True


def _stirrup_option(required_av_s: float) -> tuple[str, float, bool]:
    candidates = []
    for diameter in (6, 8, 10, 12):
        area = math.pi * diameter**2 / 4
        for legs in (2, 4):
            for spacing in (100, 125, 150, 175, 200):
                provided = legs * area / spacing
                if provided + 1e-12 >= required_av_s:
                    candidates.append((provided - required_av_s, spacing, f"{legs}肢Φ{diameter}@{spacing}", provided))
    if not candidates:
        return "箍筋方案不足，需人工调整截面", 0.0, False
    _, _, name, provided = min(candidates)
    return name, provided, True


def _t_section_required_as(moment_kN_m: float, fc: float, fy: float, b_mm: float, bf_mm: float, hf_mm: float, h0_mm: float) -> tuple[float, float, str]:
    """课程设计 T 形截面判断；返回 As、x 和第一/第二类说明。"""
    if bf_mm < b_mm or min(hf_mm, h0_mm) <= 0:
        raise ValueError("T 形截面的 bf' 不得小于腹板宽度，且 hf、h0 必须大于 0")
    flange_capacity = fc * bf_mm * hf_mm * (h0_mm - hf_mm / 2) / 1_000_000
    if moment_kN_m <= flange_capacity + 1e-9:
        area, x = calculate_required_as(moment_kN_m, fc, fy, bf_mm, h0_mm)
        return area, x, "第一类T形截面（受压区位于翼缘内）"
    flange_overhang = fc * (bf_mm - b_mm) * hf_mm * (h0_mm - hf_mm / 2) / 1_000_000
    residual = moment_kN_m - flange_overhang
    area_web, x = calculate_required_as(residual, fc, fy, b_mm, h0_mm)
    area = area_web + fc * (bf_mm - b_mm) * hf_mm / fy
    return area, x, "第二类T形截面（受压区进入腹板）"


def design_control_sections(
    envelope: MemberEnvelopeResult,
    member_kind: str,
    b_mm: float,
    h_mm: float,
    h0_mm: float,
    fc: float,
    fy: float,
    fyv: float | None = None,
    flange_width_mm: float | None = None,
    flange_thickness_mm: float | None = None,
) -> pd.DataFrame:
    """对每个控制截面的正、负弯矩分别给出独立方案。"""
    slab = member_kind == "slab"
    min_ratio = COURSE_SPEC.min_longitudinal_ratio
    as_min = min_ratio * b_mm * h_mm
    as_max = COURSE_SPEC.max_longitudinal_ratio * b_mm * h0_mm
    rows: list[dict] = []
    for _, force in envelope.control_df.iterrows():
        moments = [
            ("正弯矩", float(force["最大正弯矩 (kN·m)"]), "板底" if slab else "梁底", force["正弯矩控制工况"]),
            ("负弯矩", float(force["最大负弯矩 (kN·m)"]), "板面" if slab else "梁顶", force["负弯矩控制工况"]),
        ]
        nonzero = [item for item in moments if abs(item[1]) > 1e-8]
        if not nonzero:
            nonzero = [moments[0]]
        shear = max(abs(float(force["最大正剪力 (kN)"])), abs(float(force["最大负剪力 (kN)"])))
        for moment_type, moment, tension, case in nonzero:
            section_type = "矩形截面"
            bf_used = b_mm
            try:
                if not slab and moment_type == "正弯矩":
                    hf = float(flange_thickness_mm or max(h_mm - h0_mm, 1.0))
                    bf_used = float(flange_width_mm or (b_mm + 12 * hf))
                    calculated_as, compression_x, section_type = _t_section_required_as(abs(moment), fc, fy, b_mm, bf_used, hf, h0_mm)
                else:
                    calculated_as, compression_x = calculate_required_as(abs(moment), fc, fy, b_mm, h0_mm)
                    section_type = "矩形截面（支座负弯矩翼缘受拉，不计翼缘）" if not slab else "矩形板带"
                error = ""
            except ValueError as exc:
                calculated_as, compression_x = float("inf"), float("nan")
                error = str(exc)
            design_as = max(calculated_as, as_min)
            if slab:
                option, provided, over = _slab_option(design_as)
                fit_ok = provided >= design_as and design_as <= as_max
                stirrup, av_s = "不适用", 0.0
            else:
                option, provided, over, fit_ok = _beam_option(design_as, b_mm)
                _, required_av_s = estimate_stirrups(shear, fc, b_mm, h0_mm, fyv or fy)
                stirrup, av_s, stirrup_ok = _stirrup_option(required_av_s)
                fit_ok = fit_ok and stirrup_ok and design_as <= as_max
            compression_ok = math.isfinite(compression_x) and compression_x <= COURSE_SPEC.compression_limit_ratio * h0_mm + 1e-9
            fit_ok = fit_ok and compression_ok
            utilization = design_as / provided * 100 if provided > 0 and math.isfinite(design_as) else float("nan")
            notes = []
            if design_as == as_min:
                notes.append("由最小配筋控制")
            if design_as > as_max:
                notes.append("超过默认最大配筋控制值，应增大截面")
            if not compression_ok:
                notes.append(f"受压区 x>ξb h0（ξb={COURSE_SPEC.compression_limit_ratio:g}），超筋或截面不足")
            if over > 30:
                notes.append("超配率较高")
            notes.append(COURSE_SPEC.source_note)
            notes.append("锚固、截断、裂缝和规范构造需人工复核")
            if error:
                notes.insert(0, error)
            rows.append(
                {
                    "构件": force["构件类型"],
                    "跨号": int(force["跨号"]),
                    "截面编号": force["截面编号"],
                    "截面名称": force["截面名称"],
                    "x (m)": force["x (m)"],
                    "设计方向": moment_type,
                    "M (kN·m)": round(moment, 5),
                    "V设计值 (kN)": round(shear, 5),
                    "受拉位置": tension,
                    "截面类型判断": section_type,
                    "采用翼缘有效宽度 bf' (mm)": round(bf_used, 3) if not slab and moment_type == "正弯矩" else "—",
                    "计算 As (mm2/m)" if slab else "计算 As (mm2)": round(calculated_as, 3) if math.isfinite(calculated_as) else calculated_as,
                    "As,min (mm2/m)" if slab else "As,min (mm2)": round(as_min, 3),
                    "设计 As (mm2/m)" if slab else "设计 As (mm2)": round(design_as, 3) if math.isfinite(design_as) else design_as,
                    "推荐纵筋": option,
                    "实配面积 (mm2/m)" if slab else "实配面积 (mm2)": round(provided, 3),
                    "利用率 (%)": round(utilization, 2) if math.isfinite(utilization) else utilization,
                    "超配率 (%)": round(over, 2),
                    "箍筋方案": stirrup,
                    "实配 Av/s (mm2/mm)": round(av_s, 4),
                    "控制工况": case,
                    "是否满足": "满足" if fit_ok else "不满足",
                    "需人工复核事项": "；".join(notes),
                    "受压区 x (mm)": round(compression_x, 3) if math.isfinite(compression_x) else compression_x,
                    "ξb h0 (mm)": round(COURSE_SPEC.compression_limit_ratio * h0_mm, 3),
                    "抗剪公式来源": COURSE_SPEC.source_note if not slab else "不适用",
                }
            )
    return pd.DataFrame(rows)
