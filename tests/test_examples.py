"""课程设计示例参数测试。"""

import pytest

from calculations.secondary_beam import SecondaryBeamInput, calculate_secondary_beam
from calculations.main_beam import MainBeamInput, calculate_main_beam
from calculations.slab import SlabInput, calculate_slab
from calculations.loads import calculate_load_transfer
from calculations.section_estimation import estimate_all_sections
from calculations.envelope import calculate_envelope
from calculations.moment_capacity import calculate_moment_capacity
from export.export_report import build_markdown_report


def test_dead_load_standard_is_close_to_example() -> None:
    """恒载标准值应约为 2.91 kN/m2。"""
    result = calculate_slab(SlabInput())
    assert result.dead_load_standard_kN_m2 == pytest.approx(2.91, abs=0.01)


def test_line_load_design_is_close_to_example() -> None:
    """荷载设计线值应约为 7.856 kN/m。"""
    result = calculate_slab(SlabInput())
    assert result.line_load_design_kN_m == pytest.approx(7.856, abs=0.01)


def test_invalid_span_raises_error() -> None:
    """计算跨度小于等于 0 时应报错。"""
    with pytest.raises(ValueError):
        calculate_slab(SlabInput(l0_m=0))


def test_invalid_thickness_raises_error() -> None:
    """板厚小于等于 0 时应报错。"""
    with pytest.raises(ValueError):
        calculate_slab(SlabInput(h_mm=0))


def test_secondary_beam_dead_load_items_are_close_to_example() -> None:
    """次梁恒载各项应与题目给出的测试算例接近。"""
    result = calculate_secondary_beam(SecondaryBeamInput())
    assert result.slab_dead_line_load_kN_m == pytest.approx(5.82, abs=0.01)
    assert result.beam_self_weight_kN_m == pytest.approx(1.6, abs=0.01)
    assert result.beam_plaster_load_kN_m == pytest.approx(0.163, abs=0.01)
    assert result.dead_load_standard_kN_m == pytest.approx(7.583, abs=0.01)


def test_secondary_beam_design_loads_are_close_to_example() -> None:
    """次梁恒载设计值和活载设计值应与题目算例接近。"""
    result = calculate_secondary_beam(SecondaryBeamInput())
    assert result.dead_load_design_kN_m == pytest.approx(7.962, abs=0.01)
    assert result.live_load_standard_kN_m == pytest.approx(8.0, abs=0.01)
    assert result.live_load_design_kN_m == pytest.approx(9.6, abs=0.01)


def test_secondary_beam_invalid_height_raises_error() -> None:
    """次梁高度小于等于板厚时应报错。"""
    with pytest.raises(ValueError):
        calculate_secondary_beam(SecondaryBeamInput(h_mm=80, hf_mm=80))


def test_main_beam_dead_load_items_are_close_to_example() -> None:
    """主梁恒载各项应与题目给出的测试算例接近。"""
    result = calculate_main_beam(MainBeamInput())
    assert result.secondary_dead_concentrated_kN == pytest.approx(45.498, abs=0.01)
    assert result.beam_self_weight_kN == pytest.approx(8.55, abs=0.01)
    assert result.beam_plaster_load_kN == pytest.approx(0.5814, abs=0.01)
    assert result.dead_load_standard_kN == pytest.approx(54.629, abs=0.01)


def test_main_beam_design_loads_are_close_to_example() -> None:
    """主梁恒载设计值和活载设计值应与题目算例接近。"""
    result = calculate_main_beam(MainBeamInput())
    assert result.dead_load_design_kN == pytest.approx(57.36, abs=0.01)
    assert result.live_load_standard_kN == pytest.approx(48.0, abs=0.01)
    assert result.live_load_design_kN == pytest.approx(57.6, abs=0.01)


def test_main_beam_invalid_height_raises_error() -> None:
    """主梁高度小于等于板厚时应报错。"""
    with pytest.raises(ValueError):
        calculate_main_beam(MainBeamInput(h_mm=80, hf_mm=80))


def test_load_transfer_matches_course_example() -> None:
    """板到次梁、次梁到主梁的荷载传递应符合示例公式。"""
    result = calculate_load_transfer(2.91, 4.0, 2.0, 6.0)
    assert result.secondary_dead_from_slab_kN_m == pytest.approx(5.82, abs=0.01)
    assert result.secondary_live_from_slab_kN_m == pytest.approx(8.0, abs=0.01)
    assert result.main_dead_from_secondary_kN == pytest.approx(34.92, abs=0.01)
    assert result.main_live_from_secondary_kN == pytest.approx(48.0, abs=0.01)


def test_section_estimation_marks_default_beams_reasonable() -> None:
    """默认梁截面应能进入经验初估合理范围。"""
    estimates = estimate_all_sections(80, 6, 200, 400, 6, 300, 650)
    assert estimates[0].judgement == "合理"
    assert estimates[1].judgement == "合理"
    assert estimates[2].judgement in {"合理", "偏保守"}


def test_rebar_options_include_over_ratio() -> None:
    """配筋推荐应输出超配率和评价。"""
    result = calculate_slab(SlabInput())
    assert all(hasattr(item, "over_ratio_percent") for item in result.rebar_options)
    assert any(item.is_ok for item in result.rebar_options)


def test_envelope_returns_summary_for_three_control_sections() -> None:
    """简化包络应输出三个控制截面的最不利内力。"""
    _, summary = calculate_envelope(7.962, 9.6, 6.0, "line")
    assert list(summary["截面位置"]) == ["左支座", "跨中", "右支座"]


def test_moment_capacity_is_positive() -> None:
    """抵抗弯矩估算值应为正。"""
    assert calculate_moment_capacity(603.19, 9.6, 300, 200, 360) > 0


def test_markdown_report_contains_manual_review_warning() -> None:
    """半自动计算书应保留人工复核提示。"""
    report = build_markdown_report("测试计算书", {"测试表": pytest.importorskip("pandas").DataFrame({"A": [1]})})
    assert "不能替代课程设计手算" in report
