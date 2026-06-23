"""无外部图形库的剪力图绘制工具。"""

from __future__ import annotations

from charts.plot_moment import ChartArtifact, _hex_to_rgb, _png_from_points, _scale_points, _scaled_y, _svg_chart, figure_to_png_bytes


def _step_series(positions: list[float], shears: list[float]) -> tuple[list[float], list[float]]:
    """生成集中荷载剪力阶梯线。"""
    if len(positions) < 3:
        return positions, shears
    return [positions[0], positions[1], positions[1], positions[2]], [shears[0], shears[0], shears[-1], shears[-1]]


def plot_shear_diagram(
    positions: list[float],
    shears: list[float],
    labels: list[str],
    title: str,
    mode: str = "linear",
) -> ChartArtifact:
    """绘制简化控制点剪力图。"""
    if mode == "step":
        xs, ys = _step_series(positions, shears)
        return _svg_chart(
            xs,
            ys,
            labels,
            title,
            "剪力 V (kN)",
            "#dc2626",
            "kN",
            control_positions=positions,
            control_values=shears,
            control_labels=labels,
        )
    return _svg_chart(positions, shears, labels, title, "剪力 V (kN)", "#dc2626", "kN")
