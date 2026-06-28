"""矩阵刚度法连续弯矩、剪力包络图。"""

from __future__ import annotations

from io import BytesIO

from charts.plot_moment import ChartArtifact, _scale_points_to_bounds, _bounds
from calculations.force_envelope import MemberEnvelopeResult

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    go = None


def _envelope_artifact(result: MemberEnvelopeResult, force: str) -> ChartArtifact:
    df = result.envelope_df
    xs = df["x (m)"].astype(float).tolist()
    if force == "moment":
        upper_col, lower_col, title, unit = "最大弯矩 (kN·m)", "最小弯矩 (kN·m)", f"{result.model.member}矩阵刚度法弯矩包络图", "M (kN·m)"
    else:
        upper_col, lower_col, title, unit = "最大剪力 (kN)", "最小剪力 (kN)", f"{result.model.member}矩阵刚度法剪力包络图", "V (kN)"
    upper = df[upper_col].astype(float).tolist()
    lower = df[lower_col].astype(float).tolist()
    width, height = 1000, 500
    x_bounds, y_bounds = _bounds(xs), _bounds(upper + lower + [0.0])
    upper_points = _scale_points_to_bounds(xs, upper, width, height, x_bounds, y_bounds)
    lower_points = _scale_points_to_bounds(xs, lower, width, height, x_bounds, y_bounds)
    upper_line = " ".join(f"{x},{y}" for x, y in upper_points)
    lower_line = " ".join(f"{x},{y}" for x, y in lower_points)
    svg = f'''<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg"><rect width="100%" height="100%" fill="white"/><text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-weight="700">{title}</text><polyline points="{upper_line}" fill="none" stroke="#16a34a" stroke-width="3"/><polyline points="{lower_line}" fill="none" stroke="#dc2626" stroke-width="3"/><text x="{width/2}" y="{height-15}" text-anchor="middle">位置 x (m)</text><text x="20" y="{height/2}" transform="rotate(-90 20,{height/2})" text-anchor="middle">{unit}</text></svg>'''
    figure = None
    if go is not None:
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=xs, y=upper, mode="lines", name="最大包络", line={"color": "#16a34a", "width": 3}, hovertemplate="x=%{x:.3f}m<br>最大=%{y:.3f}<extra></extra>"))
        figure.add_trace(go.Scatter(x=xs, y=lower, mode="lines", name="最小包络", line={"color": "#dc2626", "width": 3}, fill="tonexty", fillcolor="rgba(37,99,235,0.10)", hovertemplate="x=%{x:.3f}m<br>最小=%{y:.3f}<extra></extra>"))
        for boundary in result.model.boundaries_m:
            figure.add_vline(x=boundary, line_color="#64748b", line_dash="dot", opacity=0.5)
        figure.add_hline(y=0, line_color="#111827", line_width=1)
        figure.update_layout(title=title, xaxis_title="位置 x (m)", yaxis_title=unit, template="plotly_white", height=500, hovermode="x unified", margin={"l": 55, "r": 25, "t": 65, "b": 50})
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    zero_y = _scale_points_to_bounds([xs[0]], [0.0], width, height, x_bounds, y_bounds)[0][1]
    draw.line((55, zero_y, width - 35, zero_y), fill="#475569", width=1)
    draw.line(upper_points, fill="#16a34a", width=3)
    draw.line(lower_points, fill="#dc2626", width=3)
    for boundary in result.model.boundaries_m:
        px = _scale_points_to_bounds([boundary], [0.0], width, height, x_bounds, y_bounds)[0][0]
        draw.line((px, 35, px, height - 55), fill="#cbd5e1", width=1)
    output = BytesIO()
    image.save(output, format="PNG")
    return ChartArtifact(svg, output.getvalue(), figure)


def plot_matrix_moment_envelope(result: MemberEnvelopeResult) -> ChartArtifact:
    return _envelope_artifact(result, "moment")


def plot_matrix_shear_envelope(result: MemberEnvelopeResult) -> ChartArtifact:
    return _envelope_artifact(result, "shear")
