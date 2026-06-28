"""矩阵刚度分析的控制截面识别与编号。"""

from __future__ import annotations

from dataclasses import dataclass

from calculations.matrix_stiffness import BeamAnalysisResult
from calculations.structural_models import ContinuousMemberModel


@dataclass(frozen=True)
class ControlSection:
    section_id: str
    member: str
    span_index: int
    name: str
    x_m: float
    side: str = "right"
    adjacent_support_index: int | None = None


def _section_code(member: str, name: str, span: int, support: int | None) -> str:
    prefix = {"板": "S", "次梁": "SB", "主梁": "MB"}.get(member, "M")
    if member in {"次梁", "主梁"}:
        support_mark = chr(ord("A") + support) if support is not None and support < 26 else f"S{(support or 0) + 1}"
        if "跨中" in name:
            return str(span + 1)
        if "支座中心" in name:
            return support_mark
        if "左支座右边缘" in name:
            return f"{support_mark}-R"
        if "右支座左边缘" in name:
            return f"{support_mark}-L"
        if "剪力" in name:
            return f"{support_mark}-V{'L' if '右端' in name else 'R'}"
        if "V=0" in name:
            return f"{span + 1}-V0"
    if "支座中心" in name and support is not None:
        return f"{prefix}-SUP{support + 1}"
    if "跨中" in name:
        return f"{prefix}-MID{span + 1}"
    return prefix


def build_control_sections(
    model: ContinuousMemberModel,
    case_results: dict[str, BeamAnalysisResult],
) -> list[ControlSection]:
    """生成跨中、支座中心/边缘、剪力和跨内 V=0 极值截面。

    支座边缘完全使用模型中的真实宽度，不再以 ``0.2L`` 截断。
    """
    boundaries = model.boundaries_m
    candidates: list[tuple[int, str, float, str, int | None]] = []
    for span, length in enumerate(model.spans_m):
        left, right = boundaries[span], boundaries[span + 1]
        left_face = left + model.support_widths_m[span] / 2
        right_face = right - model.support_widths_m[span + 1] / 2
        if left_face >= right_face - 1e-9:
            raise ValueError(
                f"{model.member}第 {span + 1} 跨净跨小于等于 0 或左右支座边缘重叠；"
                "支座边缘必须按真实宽度计算"
            )
        mid_name = "边跨跨中截面" if span in {0, len(model.spans_m) - 1} else "中跨跨中截面"
        candidates.extend(
            [
                (span, "左支座右边缘截面", left_face, "right", span),
                (span, "左端剪力控制截面", left_face, "right", span),
                (span, mid_name, (left_face + right_face) / 2, "right", None),
                (span, "右支座左边缘截面", right_face, "left", span + 1),
                (span, "右端剪力控制截面", right_face, "left", span + 1),
            ]
        )

    # 内支座中心弯矩必须独立保留；弯矩连续，统一取右侧，剪力仍由左右边缘控制。
    for support in range(1, len(boundaries) - 1):
        candidates.append((support, "内支座中心截面", boundaries[support], "right", support))

    roots_by_span: dict[int, set[float]] = {index: set() for index in range(len(model.spans_m))}
    for result in case_results.values():
        nodes = {node.node_id: node for node in result.nodes}
        end_forces = {item.element_id: item for item in result.element_end_forces}
        for element in result.elements:
            q = element.udl_down_kN_m
            if abs(q) < 1e-12:
                continue
            xi = nodes[element.node_i].x_m
            xj = nodes[element.node_j].x_m
            root = end_forces[element.element_id].shear_i_kN / q
            x = xi + root
            left_face = boundaries[element.span_index] + model.support_widths_m[element.span_index] / 2
            right_face = boundaries[element.span_index + 1] - model.support_widths_m[element.span_index + 1] / 2
            if max(xi, left_face) + 1e-7 < x < min(xj, right_face) - 1e-7:
                roots_by_span[element.span_index].add(round(x, 8))

    for span, roots in roots_by_span.items():
        for number, x in enumerate(sorted(roots), start=1):
            candidates.append((span, f"跨内 V=0 弯矩极值截面{number}", x, "right", None))

    boundaries_set = {round(value, 8) for value in boundaries}
    for point in model.point_loads:
        if round(point.x_m, 8) in boundaries_set:
            # 位于支座的集中力已经作为支座节点荷载处理，不虚构左右跨归属。
            continue
        span = model.span_at(point.x_m)
        candidates.append((span, f"{point.source}左侧", point.x_m, "left", None))
        candidates.append((span, f"{point.source}右侧", point.x_m, "right", None))

    ordered = sorted(candidates, key=lambda item: (item[2], 0 if item[3] == "left" else 1, item[0], item[1]))
    counters: dict[str, int] = {}
    sections: list[ControlSection] = []
    for item in ordered:
        base = _section_code(model.member, item[1], item[0], item[4])
        counters[base] = counters.get(base, 0) + 1
        section_id = base if base not in {"S", "SB", "MB", "M"} else f"{base}-C{counters[base]:03d}"
        # 同一支座中心若代码冲突（理论上不会）仍保持唯一。
        if any(existing.section_id == section_id for existing in sections):
            section_id = f"{section_id}-{counters[base]}"
        sections.append(ControlSection(section_id, model.member, item[0], item[1], float(item[2]), item[3], item[4]))
    return sections
