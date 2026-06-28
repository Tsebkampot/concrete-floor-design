"""Euler-Bernoulli 连续梁矩阵刚度法求解器。

统一采用 kN-m 单位制：竖向位移 ``v`` 向上为正，转角 ``theta`` 逆时针
为正，输入的均布荷载和集中力以“向下为正”。截面内力中弯矩以跨中下缘
受拉（正弯矩）为正，剪力以左截面向上为正。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class BeamNode:
    """连续梁节点。"""

    node_id: int
    x_m: float
    restrain_v: bool = False
    restrain_theta: bool = False
    label: str = ""


@dataclass(frozen=True)
class BeamElement:
    """两节点 Euler-Bernoulli 梁单元。"""

    element_id: int
    node_i: int
    node_j: int
    ei_kN_m2: float
    udl_down_kN_m: float = 0.0
    span_index: int = 0


@dataclass(frozen=True)
class NodalLoad:
    """节点荷载；``force_down_kN`` 向下为正，``moment_ccw_kN_m`` 逆时针为正。"""

    node_id: int
    force_down_kN: float = 0.0
    moment_ccw_kN_m: float = 0.0


@dataclass(frozen=True)
class ElementEndForce:
    element_id: int
    shear_i_kN: float
    moment_i_ccw_kN_m: float
    shear_j_kN: float
    moment_j_ccw_kN_m: float

    @property
    def moment_i_sagging_kN_m(self) -> float:
        return -self.moment_i_ccw_kN_m

    @property
    def moment_j_sagging_kN_m(self) -> float:
        return self.moment_j_ccw_kN_m


@dataclass(frozen=True)
class ForceSample:
    x_m: float
    moment_kN_m: float
    shear_kN: float
    element_id: int
    span_index: int


@dataclass
class BeamAnalysisResult:
    nodes: list[BeamNode]
    elements: list[BeamElement]
    stiffness_matrix: np.ndarray
    load_vector: np.ndarray
    displacements: np.ndarray
    reactions: np.ndarray
    element_end_forces: list[ElementEndForce]

    def node_displacement(self, node_id: int) -> tuple[float, float]:
        idx = _node_index(self.nodes)[node_id]
        return float(self.displacements[2 * idx]), float(self.displacements[2 * idx + 1])

    def node_reaction(self, node_id: int) -> tuple[float, float]:
        idx = _node_index(self.nodes)[node_id]
        return float(self.reactions[2 * idx]), float(self.reactions[2 * idx + 1])

    def force_at(self, x_m: float, side: str = "right") -> ForceSample:
        """返回全局坐标处内力；节点处可用 ``side='left'`` 或 ``'right'`` 取侧值。"""
        tol = 1e-9
        candidates: list[BeamElement] = []
        node_map = {n.node_id: n for n in self.nodes}
        for element in self.elements:
            xi = node_map[element.node_i].x_m
            xj = node_map[element.node_j].x_m
            if xi - tol <= x_m <= xj + tol:
                candidates.append(element)
        if not candidates:
            raise ValueError(f"坐标 x={x_m:g} m 不在连续梁范围内")
        element = candidates[-1] if side == "left" else candidates[0]
        if len(candidates) > 1:
            element = candidates[0] if side == "left" else candidates[-1]
        xi = node_map[element.node_i].x_m
        local_x = min(max(x_m - xi, 0.0), node_map[element.node_j].x_m - xi)
        end_force = next(item for item in self.element_end_forces if item.element_id == element.element_id)
        moment = (
            -end_force.moment_i_ccw_kN_m
            + end_force.shear_i_kN * local_x
            - element.udl_down_kN_m * local_x**2 / 2
        )
        shear = end_force.shear_i_kN - element.udl_down_kN_m * local_x
        return ForceSample(float(x_m), float(moment), float(shear), element.element_id, element.span_index)

    def sample(self, points_per_element: int = 41) -> list[ForceSample]:
        """沿全部单元重构真实的分段二次弯矩和分段线性剪力。"""
        if points_per_element < 2:
            raise ValueError("每单元采样点数至少为 2")
        node_map = {n.node_id: n for n in self.nodes}
        samples: list[ForceSample] = []
        for element in self.elements:
            xi = node_map[element.node_i].x_m
            xj = node_map[element.node_j].x_m
            xs = np.linspace(xi, xj, points_per_element)
            for j, x in enumerate(xs):
                side = "left" if j == len(xs) - 1 else "right"
                samples.append(self.force_at(float(x), side=side))
        return samples

    @property
    def vertical_equilibrium_error_kN(self) -> float:
        """支座反力与外荷载的竖向平衡残差。"""
        support_reactions = sum(
            self.node_reaction(node.node_id)[0] for node in self.nodes if node.restrain_v
        )
        total_down = -sum(self.load_vector[0::2])
        return float(support_reactions - total_down)

    @property
    def moment_equilibrium_error_kN_m(self) -> float:
        """全部节点外力与约束反力对全局原点的力矩平衡残差。"""
        residual = 0.0
        for index, node in enumerate(self.nodes):
            residual += (self.reactions[2 * index] + self.load_vector[2 * index]) * node.x_m
            residual += self.reactions[2 * index + 1] + self.load_vector[2 * index + 1]
        return float(residual)

    @property
    def free_vertical_residual_kN(self) -> float:
        values = [abs(self.reactions[2 * i]) for i, node in enumerate(self.nodes) if not node.restrain_v]
        return float(max(values, default=0.0))

    @property
    def free_moment_residual_kN_m(self) -> float:
        values = [abs(self.reactions[2 * i + 1]) for i, node in enumerate(self.nodes) if not node.restrain_theta]
        return float(max(values, default=0.0))


def _node_index(nodes: Iterable[BeamNode]) -> dict[int, int]:
    return {node.node_id: index for index, node in enumerate(nodes)}


def beam_element_stiffness(ei_kN_m2: float, length_m: float) -> np.ndarray:
    """返回题目指定的 4×4 梁单元刚度矩阵。"""
    if ei_kN_m2 <= 0 or length_m <= 0:
        raise ValueError("EI 和单元长度必须大于 0")
    l = float(length_m)
    return ei_kN_m2 / l**3 * np.array(
        [
            [12, 6 * l, -12, 6 * l],
            [6 * l, 4 * l**2, -6 * l, 2 * l**2],
            [-12, -6 * l, 12, -6 * l],
            [6 * l, 2 * l**2, -6 * l, 4 * l**2],
        ],
        dtype=float,
    )


def uniform_load_vector(load_down_kN_m: float, length_m: float) -> np.ndarray:
    """均布荷载的一致节点荷载向量（全局竖向向上为正）。"""
    q = float(load_down_kN_m)
    l = float(length_m)
    return np.array([-q * l / 2, -q * l**2 / 12, -q * l / 2, q * l**2 / 12], dtype=float)


def solve_continuous_beam(
    nodes: Iterable[BeamNode],
    elements: Iterable[BeamElement],
    nodal_loads: Iterable[NodalLoad] | None = None,
) -> BeamAnalysisResult:
    """组装总刚度矩阵、施加约束并求解连续梁。"""
    node_list = sorted(list(nodes), key=lambda item: item.x_m)
    element_list = list(elements)
    if len(node_list) < 2 or not element_list:
        raise ValueError("连续梁至少需要两个节点和一个单元")
    ids = [node.node_id for node in node_list]
    if len(set(ids)) != len(ids):
        raise ValueError("节点编号不能重复")
    if any(b.x_m <= a.x_m for a, b in zip(node_list, node_list[1:])):
        raise ValueError("节点坐标必须严格递增")
    element_ids = [element.element_id for element in element_list]
    if len(set(element_ids)) != len(element_ids):
        raise ValueError("单元编号 element_id 不能重复")
    index = _node_index(node_list)
    ndof = 2 * len(node_list)
    stiffness = np.zeros((ndof, ndof), dtype=float)
    loads = np.zeros(ndof, dtype=float)
    element_vectors: dict[int, np.ndarray] = {}

    for element in element_list:
        if element.node_i not in index or element.node_j not in index:
            raise ValueError(f"单元 {element.element_id} 引用了不存在的节点")
        i = index[element.node_i]
        j = index[element.node_j]
        length = node_list[j].x_m - node_list[i].x_m
        if length <= 0:
            raise ValueError(f"单元 {element.element_id} 的节点顺序或长度错误")
        k_local = beam_element_stiffness(element.ei_kN_m2, length)
        f_local = uniform_load_vector(element.udl_down_kN_m, length)
        dofs = [2 * i, 2 * i + 1, 2 * j, 2 * j + 1]
        stiffness[np.ix_(dofs, dofs)] += k_local
        loads[dofs] += f_local
        element_vectors[element.element_id] = f_local

    for load in nodal_loads or []:
        if load.node_id not in index:
            raise ValueError(f"节点荷载引用了不存在的节点 {load.node_id}")
        i = index[load.node_id]
        loads[2 * i] -= load.force_down_kN
        loads[2 * i + 1] += load.moment_ccw_kN_m

    constrained: list[int] = []
    for i, node in enumerate(node_list):
        if node.restrain_v:
            constrained.append(2 * i)
        if node.restrain_theta:
            constrained.append(2 * i + 1)
    free = np.array([i for i in range(ndof) if i not in set(constrained)], dtype=int)
    if not constrained:
        raise ValueError("结构没有任何支承约束，属于机构，无法进行矩阵刚度计算")
    displacements = np.zeros(ndof, dtype=float)
    if free.size:
        k_ff = stiffness[np.ix_(free, free)]
        try:
            condition = np.linalg.cond(k_ff)
            if not np.isfinite(condition) or condition > 1e14:
                raise np.linalg.LinAlgError
            displacements[free] = np.linalg.solve(k_ff, loads[free])
        except np.linalg.LinAlgError as exc:
            raise ValueError("总刚度矩阵奇异：支承不足、节点未连接或结构形成机构") from exc
    reactions = stiffness @ displacements - loads

    end_forces: list[ElementEndForce] = []
    for element in element_list:
        i = index[element.node_i]
        j = index[element.node_j]
        length = node_list[j].x_m - node_list[i].x_m
        dofs = [2 * i, 2 * i + 1, 2 * j, 2 * j + 1]
        values = beam_element_stiffness(element.ei_kN_m2, length) @ displacements[dofs] - element_vectors[element.element_id]
        end_forces.append(ElementEndForce(element.element_id, *map(float, values)))

    return BeamAnalysisResult(
        nodes=node_list,
        elements=element_list,
        stiffness_matrix=stiffness,
        load_vector=loads,
        displacements=displacements,
        reactions=reactions,
        element_end_forces=end_forces,
    )


def elastic_flexural_rigidity_kN_m2(
    elastic_modulus_mpa: float,
    width_mm: float,
    height_mm: float,
    stiffness_factor: float = 1.0,
) -> float:
    """按毛截面 ``I=bh³/12`` 计算 EI，并换算为 kN·m²。"""
    if min(elastic_modulus_mpa, width_mm, height_mm, stiffness_factor) <= 0:
        raise ValueError("E、截面尺寸和刚度折减系数必须大于 0")
    inertia_mm4 = width_mm * height_mm**3 / 12
    return elastic_modulus_mpa * inertia_mm4 * 1e-9 * stiffness_factor
