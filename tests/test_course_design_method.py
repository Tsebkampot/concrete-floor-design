"""小组新表课程设计系数法对账回归测试。"""

import pytest

from calculations.common import default_parameters
from calculations.course_design_method import (
    CORRECTED_LOAD_CASE,
    SCREENSHOT_LOAD_CASE,
    calculate_course_design_method,
)


def _default_result():
    return calculate_course_design_method(default_parameters().to_dict())


def test_main_beam_load_cases_are_labeled_and_match_group_sheet() -> None:
    result = _default_result()
    load_cases = result.main_load_cases_df.set_index("口径")

    assert load_cases.loc[CORRECTED_LOAD_CASE, "Gd (kN/点)"] == pytest.approx(53.938, abs=0.01)
    assert load_cases.loc[SCREENSHOT_LOAD_CASE, "Gd (kN/点)"] == pytest.approx(54.77913, abs=0.01)
    assert load_cases.loc[SCREENSHOT_LOAD_CASE, "是否采用"] == "是"
    assert load_cases["复核标记"].str.contains("需复核").all()


def test_main_beam_coefficient_method_reproduces_supplement_page_forces() -> None:
    result = _default_result()
    forces = result.main_forces_df.set_index("计算截面")

    assert forces.loc["边跨跨中 1", "内力值"] == pytest.approx(176.789, rel=0.01)
    assert forces.loc["B支座中心", "内力值"] == pytest.approx(-195.238, rel=0.01)
    assert forces.loc["B支座边缘", "内力值"] == pytest.approx(165.740, rel=0.01)
    assert forces.loc["中跨跨中 2", "内力值"] == pytest.approx(91.141, rel=0.01)
    assert forces.loc["A支座", "内力值"] == pytest.approx(90.035, rel=0.01)
    assert forces.loc["B左", "内力值"] == pytest.approx(-144.919, rel=0.01)
    assert forces.loc["B右", "内力值"] == pytest.approx(125.166, rel=0.01)
    assert "需复核" in str(forces.loc["B左", "说明"])


def test_design_internal_force_factor_reproduces_main_beam_as_values() -> None:
    result = _default_result()
    main_rebar = result.rebar_df[result.rebar_df["构件"] == "主梁"].set_index("截面")

    assert main_rebar.loc["边跨跨中 1", "γd"] == pytest.approx(1.2)
    assert main_rebar.loc["边跨跨中 1", "计算 As (mm2)"] == pytest.approx(1283.03, rel=0.02)
    assert main_rebar.loc["B支座边缘", "计算 As (mm2)"] == pytest.approx(1354.14, rel=0.02)
    assert main_rebar.loc["中跨跨中 2", "计算 As (mm2)"] == pytest.approx(659.46, rel=0.02)


def test_review_table_marks_known_group_sheet_conflicts() -> None:
    result = _default_result()
    review_text = "\n".join(result.review_df["说明"].astype(str))

    assert "300×600" in review_text
    assert "54.77913" in review_text
    assert "-1.311" in review_text
    assert result.review_df["结论"].eq("需复核").all()
