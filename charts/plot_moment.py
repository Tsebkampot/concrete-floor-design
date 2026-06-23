"""无外部图形库的弯矩图绘制工具。"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from io import BytesIO

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover - fallback for environments without plotly
    go = None


@dataclass(frozen=True)
class ChartArtifact:
    """Streamlit 可显示的 SVG 图和可下载的 PNG。"""

    svg: str
    png: bytes
    figure: object | None = None


def _scale_points(xs: list[float], ys: list[float], width: int, height: int, margin: int = 55) -> list[tuple[int, int]]:
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x == min_x:
        max_x += 1
    if max_y == min_y:
        max_y += 1
    pad_y = (max_y - min_y) * 0.15
    min_y -= pad_y
    max_y += pad_y
    points = []
    for x, y in zip(xs, ys):
        px = int(margin + (x - min_x) / (max_x - min_x) * (width - 2 * margin))
        py = int(height - margin - (y - min_y) / (max_y - min_y) * (height - 2 * margin))
        points.append((px, py))
    return points


def _bounds(values: list[float]) -> tuple[float, float]:
    lower, upper = min(values), max(values)
    if upper == lower:
        upper += 1
    pad = (upper - lower) * 0.15
    return lower - pad, upper + pad


def _scale_points_to_bounds(
    xs: list[float],
    ys: list[float],
    width: int,
    height: int,
    x_bounds: tuple[float, float],
    y_bounds: tuple[float, float],
    margin: int = 55,
) -> list[tuple[int, int]]:
    min_x, max_x = x_bounds
    min_y, max_y = y_bounds
    points = []
    for x, y in zip(xs, ys):
        px = int(margin + (x - min_x) / (max_x - min_x) * (width - 2 * margin))
        py = int(height - margin - (y - min_y) / (max_y - min_y) * (height - 2 * margin))
        points.append((px, py))
    return points


def _scaled_y(value: float, values: list[float], height: int, margin: int = 55) -> int:
    min_y, max_y = min(values), max(values)
    if max_y == min_y:
        max_y += 1
    pad_y = (max_y - min_y) * 0.15
    min_y -= pad_y
    max_y += pad_y
    return int(height - margin - (value - min_y) / (max_y - min_y) * (height - 2 * margin))


def _line_pixels(p0: tuple[int, int], p1: tuple[int, int]) -> list[tuple[int, int]]:
    x0, y0 = p0
    x1, y1 = p1
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    pixels = []
    while True:
        pixels.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return pixels


def _draw_line(image: bytearray, width: int, height: int, p0: tuple[int, int], p1: tuple[int, int], color: tuple[int, int, int]) -> None:
    for x, y in _line_pixels(p0, p1):
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                xx, yy = x + ox, y + oy
                if 0 <= xx < width and 0 <= yy < height:
                    idx = (yy * width + xx) * 3
                    image[idx : idx + 3] = bytes(color)


def _png_from_points(points: list[tuple[int, int]], width: int = 900, height: int = 480, color: tuple[int, int, int] = (37, 99, 235)) -> bytes:
    image = bytearray([255] * width * height * 3)
    axis_color = (110, 110, 110)
    _draw_line(image, width, height, (55, height // 2), (width - 35, height // 2), axis_color)
    _draw_line(image, width, height, (55, 35), (55, height - 55), axis_color)
    for p0, p1 in zip(points[:-1], points[1:]):
        _draw_line(image, width, height, p0, p1, color)
    for x, y in points:
        _draw_line(image, width, height, (x - 5, y), (x + 5, y), color)
        _draw_line(image, width, height, (x, y - 5), (x, y + 5), color)
    raw = b"".join(b"\x00" + image[y * width * 3 : (y + 1) * width * 3] for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def quadratic_interpolate(control_xs: list[float], control_ys: list[float], samples: int = 49) -> tuple[list[float], list[float]]:
    """用左支座、跨中、右支座三个控制点生成二次插值示意曲线。"""
    if len(control_xs) != 3 or len(control_ys) != 3:
        raise ValueError("二次插值需要 3 个控制点")
    x0, x1, x2 = control_xs
    y0, y1, y2 = control_ys
    xs = [x0 + (x2 - x0) * i / (samples - 1) for i in range(samples)]
    ys = []
    for x in xs:
        l0 = (x - x1) * (x - x2) / ((x0 - x1) * (x0 - x2))
        l1 = (x - x0) * (x - x2) / ((x1 - x0) * (x1 - x2))
        l2 = (x - x0) * (x - x1) / ((x2 - x0) * (x2 - x1))
        ys.append(y0 * l0 + y1 * l1 + y2 * l2)
    return xs, ys


def _svg_chart(
    positions: list[float],
    values: list[float],
    labels: list[str],
    title: str,
    y_label: str,
    color: str,
    unit: str,
    control_positions: list[float] | None = None,
    control_values: list[float] | None = None,
    control_labels: list[str] | None = None,
) -> ChartArtifact:
    width, height = 900, 480
    control_positions = control_positions or positions
    control_values = control_values or values
    control_labels = control_labels or labels
    all_xs = positions + control_positions
    all_ys = values + control_values
    x_bounds = _bounds(all_xs)
    y_bounds = _bounds(all_ys)
    points = _scale_points_to_bounds(positions, values, width, height, x_bounds, y_bounds)
    control_points = _scale_points_to_bounds(control_positions, control_values, width, height, x_bounds, y_bounds)
    polyline = " ".join(f"{x},{y}" for x, y in points)
    zero_y = int(height - 55 - (0 - y_bounds[0]) / (y_bounds[1] - y_bounds[0]) * (height - 110))
    label_nodes = []
    for (x, y), label, value in zip(control_points, control_labels, control_values):
        label_nodes.append(
            f'<circle cx="{x}" cy="{y}" r="5" fill="{color}" />'
            f'<text x="{x}" y="{y - 14}" text-anchor="middle" font-size="14">{label} {value:.2f} {unit}</text>'
        )
    svg = f"""
<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="white"/>
  <text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-weight="700">{title}</text>
  <line x1="55" y1="{zero_y}" x2="{width-35}" y2="{zero_y}" stroke="#555" stroke-width="1"/>
  <line x1="55" y1="35" x2="55" y2="{height-55}" stroke="#555" stroke-width="1"/>
  <polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="3"/>
  {''.join(label_nodes)}
  <text x="{width/2}" y="{height-14}" text-anchor="middle" font-size="14">位置 x (m)</text>
  <text x="20" y="{height/2}" transform="rotate(-90 20,{height/2})" text-anchor="middle" font-size="14">{y_label}</text>
</svg>
"""
    figure = None
    if go is not None:
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=positions,
                y=values,
                mode="lines",
                line={"color": color, "width": 3},
                name=title,
                hovertemplate="x=%{x:.3f} m<br>值=%{y:.3f}<extra></extra>",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=control_positions,
                y=control_values,
                mode="markers+text",
                marker={"color": color, "size": 9},
                text=[f"{label}<br>{value:.2f} {unit}" for label, value in zip(control_labels, control_values)],
                textposition="top center",
                name="控制截面",
                hovertemplate="控制点=%{text}<extra></extra>",
            )
        )
        _style_plotly_figure(figure, title, "位置 x (m)", y_label)
    return ChartArtifact(svg=svg, png=_png_from_points(points, width, height, _hex_to_rgb(color)), figure=figure)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def plot_moment_diagram(
    positions: list[float],
    moments: list[float],
    labels: list[str],
    title: str,
    curve_kind: str = "control_polyline",
) -> ChartArtifact:
    """绘制弯矩示意图。

    ``curve_kind='quadratic'`` 时，以 3 个控制点进行二次插值，适合板和
    次梁均布荷载下的课程设计示意曲线；其他情况采用控制点折线。
    """
    if curve_kind == "quadratic":
        curve_xs, curve_ys = quadratic_interpolate(positions, moments)
        return _svg_chart(
            curve_xs,
            curve_ys,
            labels,
            title,
            "弯矩 M (kN·m)",
            "#2563eb",
            "kN·m",
            control_positions=positions,
            control_values=moments,
            control_labels=labels,
        )
    return _svg_chart(positions, moments, labels, title, "弯矩 M (kN·m)", "#2563eb", "kN·m")


def plot_envelope_diagram(curves, max_env: list[float], min_env: list[float], labels: list[str], title: str) -> ChartArtifact:
    """绘制多活载工况和最大/最小包络线示意图。"""
    width, height = 900, 480
    positions = list(curves[0].positions)
    all_values = max_env + min_env
    for curve in curves:
        all_values.extend(curve.moments)
    x_bounds = _bounds(positions)
    y_bounds = _bounds(all_values)
    zero_y = int(height - 55 - (0 - y_bounds[0]) / (y_bounds[1] - y_bounds[0]) * (height - 110))
    max_points = _scale_points_to_bounds(positions, max_env, width, height, x_bounds, y_bounds)
    min_points = _scale_points_to_bounds(positions, min_env, width, height, x_bounds, y_bounds)
    max_line = " ".join(f"{x},{y}" for x, y in max_points)
    min_line = " ".join(f"{x},{y}" for x, y in min_points)
    colors = ["#94a3b8", "#a78bfa", "#f59e0b", "#06b6d4", "#64748b"]
    condition_nodes = []
    for idx, curve in enumerate(curves):
        pts = _scale_points_to_bounds(list(curve.positions), list(curve.moments), width, height, x_bounds, y_bounds)
        line = " ".join(f"{x},{y}" for x, y in pts)
        color = colors[idx % len(colors)]
        condition_nodes.append(f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2" opacity="0.55"/>')
        condition_nodes.append(f'<text x="{width-190}" y="{64 + idx * 20}" font-size="13" fill="{color}">{curve.pattern}</text>')
    label_nodes = []
    for (x, y), label, value in zip(max_points, labels, max_env):
        label_nodes.append(
            f'<circle cx="{x}" cy="{y}" r="5" fill="#16a34a" />'
            f'<text x="{x}" y="{y - 14}" text-anchor="middle" font-size="14">{label} {value:.2f} kN·m</text>'
        )
    svg = f"""
<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="white"/>
  <text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-weight="700">{title}</text>
  <line x1="55" y1="{zero_y}" x2="{width-35}" y2="{zero_y}" stroke="#555" stroke-width="1"/>
  <line x1="55" y1="35" x2="55" y2="{height-55}" stroke="#555" stroke-width="1"/>
  {''.join(condition_nodes)}
  <polyline points="{max_line}" fill="none" stroke="#16a34a" stroke-width="4"/>
  <polyline points="{min_line}" fill="none" stroke="#dc2626" stroke-width="4"/>
  <text x="{width-190}" y="40" font-size="13" fill="#16a34a">最大包络线</text>
  <text x="{width-190}" y="58" font-size="13" fill="#dc2626">最小包络线</text>
  {''.join(label_nodes)}
  <text x="{width/2}" y="{height-14}" text-anchor="middle" font-size="14">位置 x (m)</text>
  <text x="20" y="{height/2}" transform="rotate(-90 20,{height/2})" text-anchor="middle" font-size="14">弯矩 M (kN·m)</text>
</svg>
"""
    figure = None
    if go is not None:
        figure = go.Figure()
        colors = ["#94a3b8", "#a78bfa", "#f59e0b", "#06b6d4", "#64748b"]
        for idx, curve in enumerate(curves):
            figure.add_trace(
                go.Scatter(
                    x=list(curve.positions),
                    y=list(curve.moments),
                    mode="lines+markers",
                    line={"color": colors[idx % len(colors)], "width": 2},
                    name=curve.pattern,
                )
            )
        figure.add_trace(go.Scatter(x=positions, y=max_env, mode="lines+markers+text", name="最大包络线", line={"color": "#16a34a", "width": 4}, text=[f"{v:.2f}" for v in max_env], textposition="top center"))
        figure.add_trace(go.Scatter(x=positions, y=min_env, mode="lines+markers+text", name="最小包络线", line={"color": "#dc2626", "width": 4}, text=[f"{v:.2f}" for v in min_env], textposition="bottom center"))
        _style_plotly_figure(figure, title, "位置 x (m)", "弯矩 M (kN·m)")
    return ChartArtifact(svg=svg, png=_png_from_points(max_points, width, height, _hex_to_rgb("#16a34a")), figure=figure)


def figure_to_png_bytes(fig: ChartArtifact) -> bytes:
    """通过 BytesIO 返回图形 PNG 字节。"""
    output = BytesIO()
    output.write(fig.png)
    return output.getvalue()


def _style_plotly_figure(figure, title: str, x_title: str, y_title: str) -> None:
    """统一 Plotly 图表风格。"""
    figure.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        paper_bgcolor="#f6f8fb",
        plot_bgcolor="#ffffff",
        font={"family": "Arial, Microsoft YaHei, sans-serif", "color": "#17324d"},
        margin={"l": 56, "r": 30, "t": 62, "b": 52},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    figure.update_xaxes(title=x_title, showgrid=True, gridcolor="#e5edf5", zeroline=True, zerolinecolor="#94a3b8")
    figure.update_yaxes(title=y_title, showgrid=True, gridcolor="#e5edf5", zeroline=True, zerolinecolor="#94a3b8")
