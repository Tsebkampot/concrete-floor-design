"""多工况矩阵分析、控制截面内力和包络。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from calculations.control_sections import ControlSection, build_control_sections
from calculations.load_cases import LoadPattern, enumerate_live_load_patterns
from calculations.matrix_stiffness import BeamAnalysisResult
from calculations.structural_models import ContinuousMemberModel, analyze_member, model_to_rows


@dataclass
class MemberEnvelopeResult:
    model: ContinuousMemberModel
    patterns: list[LoadPattern]
    cases: dict[str, BeamAnalysisResult]
    control_sections: list[ControlSection]
    control_df: pd.DataFrame
    envelope_df: pd.DataFrame
    node_df: pd.DataFrame
    element_df: pd.DataFrame
    load_case_df: pd.DataFrame
    displacement_df: pd.DataFrame
    reaction_df: pd.DataFrame
    end_force_df: pd.DataFrame
    stiffness_summary_df: pd.DataFrame


def _control_table(
    model: ContinuousMemberModel,
    patterns: list[LoadPattern],
    cases: dict[str, BeamAnalysisResult],
    sections: list[ControlSection],
) -> pd.DataFrame:
    rows: list[dict] = []
    support_nodes = [node for node in next(iter(cases.values())).nodes if node.restrain_v]
    for section in sections:
        values = []
        for pattern in patterns:
            force = cases[pattern.name].force_at(section.x_m, section.side)
            values.append((pattern.name, force.moment_kN_m, force.shear_kN))
        max_m = max(values, key=lambda item: item[1])
        min_m = min(values, key=lambda item: item[1])
        max_v = max(values, key=lambda item: item[2])
        min_v = min(values, key=lambda item: item[2])
        reaction_value = 0.0
        reaction_case = "-"
        if section.adjacent_support_index is not None and section.adjacent_support_index < len(support_nodes):
            support_node = support_nodes[section.adjacent_support_index]
            reaction_pairs = [
                (pattern.name, cases[pattern.name].node_reaction(support_node.node_id)[0]) for pattern in patterns
            ]
            reaction_case, reaction_value = max(reaction_pairs, key=lambda item: abs(item[1]))
        positive_value = max(max_m[1], 0.0)
        negative_value = min(min_m[1], 0.0)
        controlling_m = max((max_m, min_m), key=lambda item: abs(item[1]))
        tension = "板底/梁底" if controlling_m[1] >= 0 else "板面/梁顶"
        rows.append(
            {
                "构件类型": model.member,
                "跨号": section.span_index + 1,
                "截面编号": section.section_id,
                "截面名称": section.name,
                "x (m)": round(section.x_m, 5),
                "取值侧": "左侧" if section.side == "left" else "右侧",
                "最大正弯矩 (kN·m)": round(positive_value, 5),
                "正弯矩控制工况": max_m[0] if positive_value > 1e-8 else "—",
                "最大负弯矩 (kN·m)": round(negative_value, 5),
                "负弯矩控制工况": min_m[0] if negative_value < -1e-8 else "—",
                "最大正剪力 (kN)": round(max(max_v[2], 0.0), 5),
                "正剪力控制工况": max_v[0],
                "最大负剪力 (kN)": round(min(min_v[2], 0.0), 5),
                "负剪力控制工况": min_v[0],
                "邻近支座最大反力 (kN)": round(reaction_value, 5),
                "反力控制工况": reaction_case,
                "控制受拉位置": tension,
            }
        )
    return pd.DataFrame(rows)


def _dense_envelope(patterns: list[LoadPattern], cases: dict[str, BeamAnalysisResult]) -> pd.DataFrame:
    by_case = {pattern.name: cases[pattern.name].sample(41) for pattern in patterns}
    xs = sorted({round(item.x_m, 8) for values in by_case.values() for item in values})
    first = next(iter(cases.values()))
    internal_nodes = {round(node.x_m, 8) for node in first.nodes[1:-1]}
    positions = []
    for x in xs:
        if x in internal_nodes:
            positions.append((x, "left"))
        positions.append((x, "right"))
    rows = []
    for x, side in positions:
        values = []
        for pattern in patterns:
            force = cases[pattern.name].force_at(x, side)
            values.append((pattern.name, force.moment_kN_m, force.shear_kN))
        max_m = max(values, key=lambda item: item[1])
        min_m = min(values, key=lambda item: item[1])
        max_v = max(values, key=lambda item: item[2])
        min_v = min(values, key=lambda item: item[2])
        rows.append(
            {
                "x (m)": x,
                "取值侧": "左侧" if side == "left" else "右侧",
                "最大弯矩 (kN·m)": max_m[1],
                "最小弯矩 (kN·m)": min_m[1],
                "最大剪力 (kN)": max_v[2],
                "最小剪力 (kN)": min_v[2],
                "最大弯矩工况": max_m[0],
                "最小弯矩工况": min_m[0],
                "最大剪力工况": max_v[0],
                "最小剪力工况": min_v[0],
            }
        )
    return pd.DataFrame(rows)


def analyze_member_envelope(
    model: ContinuousMemberModel,
    automatic_patterns: bool = True,
    manual_live_spans: set[int] | None = None,
) -> MemberEnvelopeResult:
    patterns = enumerate_live_load_patterns(len(model.spans_m), automatic_patterns, manual_live_spans)
    cases = {pattern.name: analyze_member(model, set(pattern.active_live_spans), include_dead=True) for pattern in patterns}
    return build_member_envelope_from_cases(model, patterns, cases)


def build_member_envelope_from_cases(
    model: ContinuousMemberModel,
    patterns: list[LoadPattern],
    cases: dict[str, BeamAnalysisResult],
) -> MemberEnvelopeResult:
    """由同名预计算全局工况组装包络，供逐级传力链复用。"""
    if not patterns or set(cases) != {pattern.name for pattern in patterns}:
        raise ValueError("预计算工况名称必须与全局荷载工况一一对应")
    sections = build_control_sections(model, cases)
    control_df = _control_table(model, patterns, cases, sections)
    envelope_df = _dense_envelope(patterns, cases)
    node_rows, element_rows = model_to_rows(model)

    displacement_rows = []
    reaction_rows = []
    end_force_rows = []
    for pattern in patterns:
        result = cases[pattern.name]
        for node in result.nodes:
            v, theta = result.node_displacement(node.node_id)
            rv, rm = result.node_reaction(node.node_id)
            displacement_rows.append({"工况": pattern.name, "节点": node.node_id, "x (m)": node.x_m, "v (m)": v, "theta (rad)": theta})
            if node.restrain_v or node.restrain_theta:
                reaction_rows.append({"工况": pattern.name, "节点": node.node_id, "x (m)": node.x_m, "竖向反力 (kN)": rv, "反力矩 (kN·m)": rm})
        element_map = {item.element_id: item for item in result.elements}
        for force in result.element_end_forces:
            element = element_map[force.element_id]
            end_force_rows.append(
                {
                    "工况": pattern.name,
                    "单元": force.element_id,
                    "跨号": element.span_index + 1,
                    "Vi (kN)": force.shear_i_kN,
                    "Mi截面 (kN·m)": force.moment_i_sagging_kN_m,
                    "Vj节点力 (kN)": force.shear_j_kN,
                    "Mj截面 (kN·m)": force.moment_j_sagging_kN_m,
                }
            )
    first = next(iter(cases.values()))
    constrained = set()
    for index, node in enumerate(first.nodes):
        if node.restrain_v:
            constrained.add(2 * index)
        if node.restrain_theta:
            constrained.add(2 * index + 1)
    free = np.array([index for index in range(first.stiffness_matrix.shape[0]) if index not in constrained], dtype=int)
    condition = float(np.linalg.cond(first.stiffness_matrix[np.ix_(free, free)])) if free.size else 1.0
    max_vertical = max(abs(case.vertical_equilibrium_error_kN) for case in cases.values())
    max_moment = max(abs(case.moment_equilibrium_error_kN_m) for case in cases.values())
    max_free_v = max(case.free_vertical_residual_kN for case in cases.values())
    max_free_m = max(case.free_moment_residual_kN_m for case in cases.values())
    stiffness_summary = pd.DataFrame(
        [[first.stiffness_matrix.shape[0], first.stiffness_matrix.shape[1], bool(np.allclose(first.stiffness_matrix, first.stiffness_matrix.T)), float(condition), max_vertical, max_moment, max_free_v, max_free_m]],
        columns=["矩阵行数", "矩阵列数", "是否对称", "条件数参考值", "竖向平衡残差 (kN)", "整体力矩平衡残差 (kN·m)", "自由节点竖向力残差 (kN)", "自由节点弯矩残差 (kN·m)"],
    )
    return MemberEnvelopeResult(
        model=model,
        patterns=patterns,
        cases=cases,
        control_sections=sections,
        control_df=control_df,
        envelope_df=envelope_df,
        node_df=pd.DataFrame(node_rows),
        element_df=pd.DataFrame(element_rows),
        load_case_df=pd.DataFrame([{"工况": p.name, "活载跨": ",".join(str(i + 1) for i in sorted(p.active_live_spans)) or "无", "说明": p.description} for p in patterns]),
        displacement_df=pd.DataFrame(displacement_rows),
        reaction_df=pd.DataFrame(reaction_rows),
        end_force_df=pd.DataFrame(end_force_rows),
        stiffness_summary_df=stiffness_summary,
    )
