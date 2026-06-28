"""只读校核报告对应的回归测试。"""

from io import BytesIO
from types import SimpleNamespace
import zipfile

import pandas as pd
import pytest
from openpyxl import load_workbook

import app
from calculations.common import default_parameters
from calculations.force_envelope import analyze_member_envelope
from calculations.matrix_stiffness import BeamElement, BeamNode, solve_continuous_beam
from calculations.project_analysis import analyze_project_matrix, parse_supports, slab_support_line_reactions
from calculations.rebar import recommend_longitudinal_rebar
from calculations.section_design import design_control_sections
from calculations.slab import SlabInput, calculate_loads
from calculations.structural_models import ContinuousMemberModel, MemberPointLoad, analyze_member
from charts.plot_control_sections import plot_control_section_diagram
from export.export_excel import build_excel_workbook
from export.export_word import build_word_report


EI = 100_000.0


def _slab_model(strip_width: float, spans=(2.0, 2.0, 2.0)) -> ContinuousMemberModel:
    return ContinuousMemberModel(
        "板", spans, EI * strip_width,
        tuple(3.0 * strip_width for _ in spans), tuple(4.0 * strip_width for _ in spans),
        tuple(0.2 for _ in range(len(spans) + 1)), tuple("pin" for _ in range(len(spans) + 1)),
    )


@pytest.mark.parametrize("strip_width", [0.5, 1.0, 2.0])
def test_slab_transfer_reaction_is_independent_of_strip_width(strip_width: float) -> None:
    model = _slab_model(strip_width)
    case = analyze_member(model, set(range(3)), include_dead=True)
    values = slab_support_line_reactions(model, case, strip_width)
    reference_model = _slab_model(1.0)
    reference = slab_support_line_reactions(reference_model, analyze_member(reference_model, set(range(3)), True), 1.0)
    assert values == pytest.approx(reference)


def test_unequal_slab_support_reactions_are_not_replaced_by_one_maximum() -> None:
    model = _slab_model(1.0, (1.5, 2.0, 2.5))
    reactions = slab_support_line_reactions(model, analyze_member(model, set(range(3)), True), 1.0)
    assert len({round(value, 5) for value in reactions}) > 1


def test_global_case_name_is_continuous_through_three_levels() -> None:
    project = analyze_project_matrix(default_parameters().to_dict(), calculate_loads(SlabInput()))
    names = set(project.global_case_df["全局工况"])
    assert {"G", "Q", "G+Q[1,2,3]"}.issubset(names)
    assert names == set(project.slab.cases) == set(project.secondary.cases) == set(project.main.cases)
    assert set(project.transfer_df["全局工况"]) == names
    assert project.transfer_df["荷载来源"].str.contains("板支承线").all()


def test_support_center_and_true_faces_are_control_sections() -> None:
    model = ContinuousMemberModel("次梁", (5.0, 5.0), EI, (8.0, 8.0), (4.0, 4.0), (0.3, 0.4, 0.3), ("pin",) * 3)
    envelope = analyze_member_envelope(model)
    centers = [s for s in envelope.control_sections if s.name == "内支座中心截面"]
    assert centers and centers[0].x_m == pytest.approx(5.0)
    left_face = next(s for s in envelope.control_sections if s.name == "右支座左边缘截面" and s.span_index == 0)
    right_face = next(s for s in envelope.control_sections if s.name == "左支座右边缘截面" and s.span_index == 1)
    assert left_face.x_m == pytest.approx(5.0 - 0.4 / 2)
    assert right_face.x_m == pytest.approx(5.0 + 0.4 / 2)
    center_row = envelope.control_df[envelope.control_df["截面名称"] == "内支座中心截面"]
    assert not center_row.empty and (center_row["最大负弯矩 (kN·m)"] < 0).any()


def test_overlapping_support_faces_raise_instead_of_clipping_to_point_two_l() -> None:
    with pytest.raises(ValueError, match="净跨|重叠"):
        ContinuousMemberModel("次梁", (0.5,), EI, (1.0,), (0.0,), (0.5, 0.5), ("pin", "pin"))


def test_secondary_and_main_control_diagrams_use_distinct_directions() -> None:
    project = analyze_project_matrix(default_parameters().to_dict(), calculate_loads(SlabInput()))
    secondary_chart = plot_control_section_diagram(project.secondary)
    main_chart = plot_control_section_diagram(project.main)
    assert "次梁控制截面示意图（30m方向）" in secondary_chart.svg
    assert "主梁控制截面示意图（18m方向）" in main_chart.svg
    assert project.secondary.model.boundaries_m[-1] == pytest.approx(30.0)
    assert project.main.model.boundaries_m[-1] == pytest.approx(18.0)
    assert all(mark in secondary_chart.svg for mark in (">1<", ">B<", ">2<", ">C<", ">3<"))


def test_support_count_mismatch_is_explicit_error() -> None:
    with pytest.raises(ValueError, match="数量应为 4"):
        parse_supports("fixed,pin", 3, "次梁支承条件")


def test_failed_input_invalidates_current_result_and_blocks_export() -> None:
    state = SimpleNamespace(current_results={"old": True}, current_tables={"old": True}, latest_results={"old": True}, calculation_valid=True)
    app.invalidate_current_results(state)
    assert state.current_results is None
    assert not app.current_results_are_exportable(state)
    assert state.latest_results == {"old": True}


def test_extremely_narrow_beam_has_no_satisfactory_bar_layout() -> None:
    options = recommend_longitudinal_rebar(200.0, b_mm=50.0)
    assert options and not any(option.is_ok for option in options)
    assert all("不可布置" in option.evaluation or option.area_mm2 < 200 for option in options)


def test_positive_beam_moment_uses_t_section_and_negative_uses_rectangle() -> None:
    model = ContinuousMemberModel("次梁", (5.0, 5.0), EI, (10.0, 10.0), (5.0, 5.0), (0.3, 0.3, 0.3), ("pin",) * 3)
    envelope = analyze_member_envelope(model)
    design = design_control_sections(envelope, "beam", 250, 500, 450, 11.9, 300, 270, flange_width_mm=1000, flange_thickness_mm=100)
    assert design.loc[design["设计方向"] == "正弯矩", "截面类型判断"].str.contains("T形截面").all()
    assert design.loc[design["设计方向"] == "负弯矩", "截面类型判断"].str.contains("矩形截面").all()
    assert design["抗剪公式来源"].str.contains("需人工复核").all()


def test_high_moment_reports_compression_zone_limit_failure() -> None:
    model = ContinuousMemberModel("次梁", (4.0,), EI, (450.0,), (0.0,), (0.2, 0.2), ("pin", "pin"))
    envelope = analyze_member_envelope(model)
    design = design_control_sections(envelope, "beam", 200, 400, 350, 9.6, 300, 210, flange_width_mm=200, flange_thickness_mm=80)
    assert (design["是否满足"] == "不满足").any()
    assert design["需人工复核事项"].str.contains("ξb|受压区|截面不足").any()


def test_duplicate_element_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="element_id"):
        solve_continuous_beam(
            [BeamNode(0, 0, True), BeamNode(1, 2), BeamNode(2, 4, True)],
            [BeamElement(1, 0, 1, EI), BeamElement(1, 1, 2, EI)],
        )


def test_point_load_at_support_is_treated_as_support_node_load() -> None:
    model = ContinuousMemberModel(
        "主梁", (4.0, 4.0), EI, (0.0, 0.0), (0.0, 0.0), (0.2, 0.2, 0.2), ("pin",) * 3,
        (MemberPointLoad(4.0, 0.0, 10.0, "支座节点荷载"),),
    )
    left = analyze_member(model, {0}, include_dead=False)
    right = analyze_member(model, {1}, include_dead=False)
    assert sum(abs(value) for value in left.load_vector) > 0
    assert sum(abs(value) for value in right.load_vector) > 0


def test_excel_sheet_names_remain_unique_after_truncation() -> None:
    tables = {
        "这是一个非常长且截断后相同的工作表名称_A": pd.DataFrame({"A": [1]}),
        "这是一个非常长且截断后相同的工作表名称_B": pd.DataFrame({"A": [2]}),
    }
    data = build_excel_workbook(tables)
    assert zipfile.is_zipfile(BytesIO(data))
    workbook = load_workbook(BytesIO(data), read_only=True)
    assert len(workbook.sheetnames) == len(set(workbook.sheetnames)) == 2


def test_word_wide_table_is_split_into_readable_subtables() -> None:
    data = build_word_report("宽表回归", {"宽表": pd.DataFrame([{f"列{i}": i for i in range(22)}])})
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "续表（同一数据表按列拆分）" in xml
    assert xml.count("<w:gridCol") >= 22
