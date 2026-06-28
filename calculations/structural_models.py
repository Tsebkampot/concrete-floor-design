"""板带、次梁和主梁的连续梁模型构建。"""

from __future__ import annotations

from dataclasses import dataclass, field

from calculations.matrix_stiffness import (
    BeamAnalysisResult,
    BeamElement,
    BeamNode,
    NodalLoad,
    solve_continuous_beam,
)


@dataclass(frozen=True)
class MemberPointLoad:
    x_m: float
    dead_down_kN: float = 0.0
    live_down_kN: float = 0.0
    source: str = "集中荷载"


@dataclass(frozen=True)
class ContinuousMemberModel:
    member: str
    spans_m: tuple[float, ...]
    ei_kN_m2: float
    dead_udl_kN_m: tuple[float, ...]
    live_udl_kN_m: tuple[float, ...]
    support_widths_m: tuple[float, ...]
    support_conditions: tuple[str, ...] = field(default_factory=tuple)
    point_loads: tuple[MemberPointLoad, ...] = field(default_factory=tuple)
    direction_name: str = "计算方向"

    def __post_init__(self) -> None:
        n = len(self.spans_m)
        if not n or any(length <= 0 for length in self.spans_m):
            raise ValueError(f"{self.member}至少需要一跨且跨度必须大于 0")
        if len(self.dead_udl_kN_m) != n or len(self.live_udl_kN_m) != n:
            raise ValueError(f"{self.member}各跨荷载数量必须与跨数一致")
        if len(self.support_widths_m) != n + 1:
            raise ValueError(f"{self.member}支座宽度数量应为跨数加一")
        if self.support_conditions and len(self.support_conditions) != n + 1:
            raise ValueError(f"{self.member}支承条件数量应为跨数加一")
        if self.ei_kN_m2 <= 0:
            raise ValueError(f"{self.member}的 EI 必须大于 0")
        for index, length in enumerate(self.spans_m):
            if (self.support_widths_m[index] + self.support_widths_m[index + 1]) / 2 >= length - 1e-9:
                raise ValueError(
                    f"{self.member}第 {index + 1} 跨净跨小于等于 0 或左右支座边缘重叠；"
                    "请检查跨度和真实支座宽度"
                )

    @property
    def boundaries_m(self) -> tuple[float, ...]:
        values = [0.0]
        for span in self.spans_m:
            values.append(values[-1] + span)
        return tuple(values)

    def span_at(self, x_m: float) -> int:
        boundaries = self.boundaries_m
        for index in range(len(self.spans_m)):
            if boundaries[index] - 1e-9 <= x_m <= boundaries[index + 1] + 1e-9:
                return index
        raise ValueError(f"坐标 x={x_m:g} m 超出{self.member}范围")

    def point_live_is_active(self, x_m: float, active_spans: set[int]) -> bool:
        """集中力位于支座节点时按相邻任一活载跨处理，不再静默归入左跨。"""
        boundaries = self.boundaries_m
        for support_index, boundary in enumerate(boundaries):
            if abs(x_m - boundary) <= 1e-9:
                adjacent = {support_index - 1, support_index}
                return bool(active_spans.intersection(i for i in adjacent if 0 <= i < len(self.spans_m)))
        return self.span_at(x_m) in active_spans


def _topology(model: ContinuousMemberModel) -> tuple[list[BeamNode], list[tuple[int, int, int]]]:
    """返回节点及 ``(node_i, node_j, span_index)`` 分段。"""
    boundaries = model.boundaries_m
    coordinates = set(boundaries)
    total = boundaries[-1]
    for point in model.point_loads:
        if point.x_m < -1e-9 or point.x_m > total + 1e-9:
            raise ValueError(f"{model.member}集中荷载位置 {point.x_m:g} m 超出构件范围")
        coordinates.add(round(point.x_m, 10))
    xs = sorted(coordinates)
    boundary_index = {round(x, 10): i for i, x in enumerate(boundaries)}
    conditions = model.support_conditions or tuple("pin" for _ in boundaries)
    nodes: list[BeamNode] = []
    for node_id, x in enumerate(xs):
        support_index = boundary_index.get(round(x, 10))
        is_support = support_index is not None
        condition = conditions[support_index] if is_support else "free"
        if condition not in {"pin", "roller", "fixed", "free"}:
            raise ValueError(f"不支持的支承条件：{condition}")
        nodes.append(
            BeamNode(
                node_id,
                float(x),
                restrain_v=is_support and condition != "free",
                restrain_theta=is_support and condition == "fixed",
                label=f"支座{support_index + 1}" if is_support else "集中力节点",
            )
        )
    segments: list[tuple[int, int, int]] = []
    for i in range(len(nodes) - 1):
        mid = (nodes[i].x_m + nodes[i + 1].x_m) / 2
        segments.append((nodes[i].node_id, nodes[i + 1].node_id, model.span_at(mid)))
    return nodes, segments


def analyze_member(
    model: ContinuousMemberModel,
    active_live_spans: set[int] | None = None,
    include_dead: bool = True,
) -> BeamAnalysisResult:
    """按指定活载跨集合分析一个构件。"""
    active = active_live_spans or set()
    nodes, segments = _topology(model)
    elements: list[BeamElement] = []
    for element_id, (node_i, node_j, span_index) in enumerate(segments):
        q = model.dead_udl_kN_m[span_index] if include_dead else 0.0
        if span_index in active:
            q += model.live_udl_kN_m[span_index]
        elements.append(BeamElement(element_id, node_i, node_j, model.ei_kN_m2, q, span_index))
    node_by_x = {round(node.x_m, 10): node.node_id for node in nodes}
    nodal_loads: list[NodalLoad] = []
    for point in model.point_loads:
        value = point.dead_down_kN if include_dead else 0.0
        if model.point_live_is_active(point.x_m, active):
            value += point.live_down_kN
        if abs(value) > 1e-12:
            nodal_loads.append(NodalLoad(node_by_x[round(point.x_m, 10)], value))
    return solve_continuous_beam(nodes, elements, nodal_loads)


def support_reactions(result: BeamAnalysisResult) -> list[float]:
    return [result.node_reaction(node.node_id)[0] for node in result.nodes if node.restrain_v]


def model_to_rows(model: ContinuousMemberModel) -> tuple[list[dict], list[dict]]:
    nodes, segments = _topology(model)
    node_rows = [
        {
            "节点": node.node_id,
            "x (m)": node.x_m,
            "竖向约束": "约束" if node.restrain_v else "自由",
            "转角约束": "约束" if node.restrain_theta else "自由",
            "说明": node.label,
        }
        for node in nodes
    ]
    element_rows = []
    node_map = {node.node_id: node for node in nodes}
    for element_id, (node_i, node_j, span_index) in enumerate(segments):
        element_rows.append(
            {
                "单元": element_id,
                "起点节点": node_i,
                "终点节点": node_j,
                "跨号": span_index + 1,
                "长度 (m)": node_map[node_j].x_m - node_map[node_i].x_m,
                "EI (kN·m2)": model.ei_kN_m2,
            }
        )
    return node_rows, element_rows
