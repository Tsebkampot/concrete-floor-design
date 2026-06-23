"""无外部图形库的抵抗弯矩图绘制工具。"""

from __future__ import annotations

from charts.plot_moment import (
    ChartArtifact,
    _bounds,
    _hex_to_rgb,
    _png_from_points,
    _scale_points_to_bounds,
    _style_plotly_figure,
)

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    go = None


def plot_resisting_moment_diagram(
    positions: list[float],
    design_moments: list[float],
    capacities: list[float],
    labels: list[str],
    title: str,
) -> ChartArtifact:
    """叠加显示设计弯矩和分段抵抗弯矩。"""
    width, height = 900, 480
    all_values = design_moments + capacities
    x_bounds = _bounds(positions)
    y_bounds = _bounds(all_values)
    design_points = _scale_points_to_bounds(positions, design_moments, width, height, x_bounds, y_bounds)
    span = positions[-1] - positions[0]
    left_limit = positions[0] + span * 0.25
    right_limit = positions[-1] - span * 0.25
    cap_xs = [positions[0], left_limit, left_limit, right_limit, right_limit, positions[-1]]
    cap_ys = [capacities[0], capacities[0], capacities[1], capacities[1], capacities[-1], capacities[-1]]
    capacity_points = _scale_points_to_bounds(cap_xs, cap_ys, width, height, x_bounds, y_bounds)
    control_capacity_points = _scale_points_to_bounds(positions, capacities, width, height, x_bounds, y_bounds)
    zero_y = int(height - 55 - (0 - y_bounds[0]) / (y_bounds[1] - y_bounds[0]) * (height - 110))
    design_polyline = " ".join(f"{x},{y}" for x, y in design_points)
    capacity_polyline = " ".join(f"{x},{y}" for x, y in capacity_points)
    nodes = []
    for (x, y), label, m, mu in zip(control_capacity_points, labels, design_moments, capacities):
        nodes.append(
            f'<circle cx="{x}" cy="{y}" r="5" fill="#16a34a" />'
            f'<text x="{x}" y="{y - 14}" text-anchor="middle" font-size="14">{label} M={m:.1f}, Mu={mu:.1f}</text>'
        )
    svg = f"""
<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="white"/>
  <text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-weight="700">{title}</text>
  <line x1="55" y1="{zero_y}" x2="{width-35}" y2="{zero_y}" stroke="#555" stroke-width="1"/>
  <line x1="55" y1="35" x2="55" y2="{height-55}" stroke="#555" stroke-width="1"/>
  <polyline points="{design_polyline}" fill="none" stroke="#2563eb" stroke-width="3"/>
  <polyline points="{capacity_polyline}" fill="none" stroke="#16a34a" stroke-width="3"/>
  <text x="{width-220}" y="60" font-size="14" fill="#2563eb">设计弯矩 M</text>
  <text x="{width-220}" y="82" font-size="14" fill="#16a34a">分段抵抗弯矩 Mu</text>
  {''.join(nodes)}
  <text x="{width/2}" y="{height-14}" text-anchor="middle" font-size="14">位置 x (m)</text>
</svg>
"""
    figure = None
    if go is not None:
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=positions,
                y=design_moments,
                mode="lines+markers",
                name="设计弯矩 M",
                line={"color": "#2563eb", "width": 3},
            )
        )
        figure.add_trace(
            go.Scatter(
                x=cap_xs,
                y=cap_ys,
                mode="lines",
                name="分段抵抗弯矩 Mu",
                line={"color": "#16a34a", "width": 4, "shape": "hv"},
            )
        )
        figure.add_trace(
            go.Scatter(
                x=positions,
                y=capacities,
                mode="markers+text",
                name="控制截面承载力",
                marker={"color": "#16a34a", "size": 9},
                text=[f"{label}<br>Mu={mu:.1f}" for label, mu in zip(labels, capacities)],
                textposition="top center",
            )
        )
        _style_plotly_figure(figure, title, "位置 x (m)", "弯矩 (kN·m)")
    png = _png_from_points(capacity_points, width, height, _hex_to_rgb("#16a34a"))
    return ChartArtifact(svg=svg, png=png, figure=figure)
