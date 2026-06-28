"""矩阵刚度法、内力包络、逐截面配筋和成果导出测试。"""

import importlib
from io import BytesIO
import zipfile

import numpy as np
import pandas as pd
import pytest

from calculations.common import default_parameters
from calculations.force_envelope import analyze_member_envelope
from calculations.matrix_stiffness import BeamElement, BeamNode, NodalLoad, solve_continuous_beam
from calculations.project_analysis import analyze_project_matrix, member_tables
from calculations.section_design import design_control_sections
from calculations.slab import SlabInput, calculate_loads
from calculations.structural_models import ContinuousMemberModel
from charts.plot_control_sections import plot_control_section_diagram
from export.export_excel import build_excel_workbook
from export.export_report import build_markdown_report
from export.export_word import build_word_report


EI = 100_000.0


def test_simple_beam_udl_benchmark() -> None:
    q, length = 10.0, 6.0
    result = solve_continuous_beam(
        [BeamNode(0, 0, True), BeamNode(1, length, True)],
        [BeamElement(0, 0, 1, EI, q)],
    )
    assert result.node_reaction(0)[0] == pytest.approx(q * length / 2)
    assert result.node_reaction(1)[0] == pytest.approx(q * length / 2)
    assert result.force_at(length / 2).moment_kN_m == pytest.approx(q * length**2 / 8)


def test_simple_beam_midpoint_load_benchmark() -> None:
    p, length = 20.0, 6.0
    result = solve_continuous_beam(
        [BeamNode(0, 0, True), BeamNode(1, length / 2), BeamNode(2, length, True)],
        [BeamElement(0, 0, 1, EI), BeamElement(1, 1, 2, EI)],
        [NodalLoad(1, p)],
    )
    assert result.node_reaction(0)[0] == pytest.approx(p / 2)
    assert result.node_reaction(2)[0] == pytest.approx(p / 2)
    assert result.force_at(length / 2, "left").moment_kN_m == pytest.approx(p * length / 4)
    assert result.force_at(length / 2, "left").shear_kN == pytest.approx(p / 2)
    assert result.force_at(length / 2, "right").shear_kN == pytest.approx(-p / 2)


def test_fixed_beam_udl_benchmark() -> None:
    q, length = 10.0, 6.0
    result = solve_continuous_beam(
        [BeamNode(0, 0, True, True), BeamNode(1, length, True, True)],
        [BeamElement(0, 0, 1, EI, q)],
    )
    assert result.force_at(0).moment_kN_m == pytest.approx(-q * length**2 / 12)
    assert result.force_at(length).moment_kN_m == pytest.approx(-q * length**2 / 12)


def test_symmetric_two_span_continuous_beam() -> None:
    result = solve_continuous_beam(
        [BeamNode(0, 0, True), BeamNode(1, 5, True), BeamNode(2, 10, True)],
        [BeamElement(0, 0, 1, EI, 8), BeamElement(1, 1, 2, EI, 8)],
    )
    assert result.node_reaction(0)[0] == pytest.approx(result.node_reaction(2)[0])
    assert result.force_at(2.5).moment_kN_m == pytest.approx(result.force_at(7.5).moment_kN_m)
    assert result.vertical_equilibrium_error_kN == pytest.approx(0, abs=1e-9)


def test_global_stiffness_is_symmetric_and_mechanism_is_rejected() -> None:
    result = solve_continuous_beam(
        [BeamNode(0, 0, True), BeamNode(1, 4, True)],
        [BeamElement(0, 0, 1, EI, 5)],
    )
    assert np.allclose(result.stiffness_matrix, result.stiffness_matrix.T)
    with pytest.raises(ValueError, match="机构"):
        solve_continuous_beam([BeamNode(0, 0), BeamNode(1, 4)], [BeamElement(0, 0, 1, EI, 5)])


def _two_span_envelope():
    model = ContinuousMemberModel(
        "次梁",
        (5.0, 5.0),
        EI,
        (8.0, 8.0),
        (6.0, 6.0),
        (0.3, 0.3, 0.3),
        ("pin", "pin", "pin"),
    )
    return analyze_member_envelope(model)


def test_envelope_has_every_control_force_and_case() -> None:
    envelope = _two_span_envelope()
    required = {"最大正弯矩 (kN·m)", "最大负弯矩 (kN·m)", "最大正剪力 (kN)", "最大负剪力 (kN)", "正弯矩控制工况", "负弯矩控制工况"}
    assert required.issubset(envelope.control_df.columns)
    assert len(envelope.patterns) == 4  # G + (2^2-1) 个活载组合
    assert envelope.control_df["截面编号"].is_unique


def test_each_control_section_gets_rebar_design() -> None:
    envelope = _two_span_envelope()
    design = design_control_sections(envelope, "beam", 250, 500, 450, 11.9, 300, 270)
    assert set(envelope.control_df["截面编号"]).issubset(set(design["截面编号"]))
    satisfied = design[design["是否满足"] == "满足"]
    assert (satisfied["实配面积 (mm2)"] >= satisfied["设计 As (mm2)"]).all()


def test_control_diagram_contains_all_section_ids() -> None:
    envelope = _two_span_envelope()
    chart = plot_control_section_diagram(envelope)
    assert chart.png.startswith(b"\x89PNG")
    assert all(section.section_id in chart.svg for section in envelope.control_sections)


def test_project_uses_reactions_for_load_transfer() -> None:
    params = default_parameters().to_dict()
    slab_loads = calculate_loads(SlabInput())
    project = analyze_project_matrix(params, slab_loads)
    assert "矩阵反力" in " ".join(project.transfer_df["来源"].astype(str))
    assert project.main.model.point_loads
    assert all(point.dead_down_kN > 0 for point in project.main.model.point_loads)


def test_manual_live_spans_and_main_point_positions() -> None:
    params = default_parameters().to_dict()
    params["automatic_live_patterns"] = False
    params["slab_live_spans_text"] = "1,3"
    params["secondary_live_spans_text"] = "2"
    params["main_live_spans_text"] = "1,3"
    params["main_point_positions_text"] = "1,5,7"
    project = analyze_project_matrix(params, calculate_loads(SlabInput()))
    assert project.slab.patterns[-1].active_live_spans == frozenset({0, 2})
    assert project.secondary.patterns[-1].active_live_spans == frozenset({1})
    assert [point.x_m for point in project.main.model.point_loads] == [1.0, 5.0, 7.0]


def test_matrix_tables_export_to_excel_word_markdown() -> None:
    envelope = _two_span_envelope()
    design = design_control_sections(envelope, "beam", 250, 500, 450, 11.9, 300, 270)
    tables = member_tables(envelope, design)
    excel = build_excel_workbook(tables)
    word = build_word_report("矩阵刚度法测试", tables)
    markdown = build_markdown_report("矩阵刚度法测试", tables)
    assert zipfile.is_zipfile(BytesIO(excel))
    assert zipfile.is_zipfile(BytesIO(word))
    assert "控制截面内力包络" in markdown


def test_streamlit_app_imports() -> None:
    module = importlib.import_module("app")
    assert callable(module.main)
