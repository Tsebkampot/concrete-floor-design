"""连续梁计算模型和控制截面位置示意图。"""

from __future__ import annotations

from io import BytesIO

from charts.plot_moment import ChartArtifact
from calculations.force_envelope import MemberEnvelopeResult

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    go = None


def plot_control_section_diagram(result: MemberEnvelopeResult) -> ChartArtifact:
    model = result.model
    total = model.boundaries_m[-1]
    width = max(1000, int(total * 52))
    height = 600
    margin = 70
    scale = lambda x: int(margin + x / total * (width - 2 * margin))
    beam_y = 170
    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" xmlns="http://www.w3.org/2000/svg">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-weight="700">{model.member}控制截面示意图（{model.direction_name}）</text>',
        f'<line x1="{margin}" y1="{beam_y}" x2="{width-margin}" y2="{beam_y}" stroke="#111827" stroke-width="7"/>',
    ]
    for index, x in enumerate(model.boundaries_m):
        px = scale(x)
        support_width = max(model.support_widths_m[index] / total * (width - 2 * margin), 10)
        svg_parts.append(f'<rect x="{px-support_width/2:.1f}" y="{beam_y+8}" width="{support_width:.1f}" height="22" fill="#94a3b8"/>')
        svg_parts.append(f'<polygon points="{px-16},{beam_y+30} {px+16},{beam_y+30} {px},{beam_y+58}" fill="#64748b"/>')
        support_label = str(index + 1)
        svg_parts.append(f'<text x="{px}" y="{beam_y+80}" text-anchor="middle" font-size="12">支座{support_label}</text>')
    for index, length in enumerate(model.spans_m):
        center = (model.boundaries_m[index] + model.boundaries_m[index + 1]) / 2
        svg_parts.append(f'<text x="{scale(center)}" y="{beam_y+115}" text-anchor="middle" font-size="13">第{index+1}跨 L={length:g}m</text>')
    for point in model.point_loads:
        px = scale(point.x_m)
        svg_parts.append(f'<line x1="{px}" y1="70" x2="{px}" y2="{beam_y-8}" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow)"/>')
        svg_parts.append(f'<text x="{px}" y="62" text-anchor="middle" font-size="11" fill="#b91c1c">{point.source}</text>')
    svg_parts.insert(2, '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#dc2626"/></marker></defs>')
    for index, section in enumerate(result.control_sections):
        px = scale(section.x_m)
        top = 120 - (index % 4) * 22
        svg_parts.append(f'<line x1="{px}" y1="{top}" x2="{px}" y2="{beam_y+8}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="5 3"/>')
        svg_parts.append(f'<text x="{px}" y="{top-4}" text-anchor="middle" font-size="10" fill="#1d4ed8">{section.section_id}</text>')
    legend_columns = 2
    legend_rows = (len(result.control_sections) + legend_columns - 1) // legend_columns
    for index, section in enumerate(result.control_sections):
        column = index // legend_rows
        row = index % legend_rows
        x = margin + column * (width - 2 * margin) / legend_columns
        y = 315 + row * 13
        svg_parts.append(f'<text x="{x:.1f}" y="{y}" font-size="9" fill="#334155">{section.section_id}｜{section.name}｜x={section.x_m:g}m</text>')
    svg_parts.append(f'<text x="{width/2}" y="{height-20}" text-anchor="middle" font-size="13">正弯矩：板底/梁底受拉；负弯矩：板面/梁顶受拉；截面位置来自实际计算提取点</text>')
    svg_parts.append('</svg>')

    figure = None
    if go is not None:
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=[0, total], y=[0, 0], mode="lines", line={"color": "#111827", "width": 8}, name="构件轴线"))
        figure.add_trace(go.Scatter(x=list(model.boundaries_m), y=[0] * len(model.boundaries_m), mode="markers+text", marker={"symbol": "triangle-up", "size": 18, "color": "#64748b"}, text=[f"支座{i+1}" for i in range(len(model.boundaries_m))], textposition="bottom center", name="支座"))
        for section in result.control_sections:
            figure.add_vline(x=section.x_m, line_dash="dot", line_color="#2563eb", opacity=0.65)
            figure.add_annotation(x=section.x_m, y=0.38, text=f"{section.section_id}<br>{section.name}", showarrow=False, textangle=-90, font={"size": 10, "color": "#1d4ed8"})
        for point in model.point_loads:
            figure.add_annotation(x=point.x_m, y=0.1, ax=point.x_m, ay=0.75, text=point.source, showarrow=True, arrowhead=2, arrowcolor="#dc2626")
        figure.update_layout(title=f"{model.member}控制截面示意图（{model.direction_name}）", xaxis_title="全局坐标 x (m)", yaxis={"visible": False, "range": [-0.35, 0.9]}, height=560, margin={"l": 35, "r": 25, "t": 70, "b": 40}, template="plotly_white", showlegend=True)
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
    try:
        font = ImageFont.truetype(font_path, 13)
        title_font = ImageFont.truetype(font_path, 22)
    except OSError:  # pragma: no cover - 非 macOS 回退
        font = ImageFont.load_default()
        title_font = font
    title = f"{model.member}控制截面示意图（{model.direction_name}）"
    draw.text((width / 2, 24), title, fill="#111827", font=title_font, anchor="mm")
    draw.line((margin, beam_y, width - margin, beam_y), fill="#111827", width=7)
    for index, x in enumerate(model.boundaries_m):
        px = scale(x)
        draw.rectangle((px - 8, beam_y + 8, px + 8, beam_y + 25), fill="#94a3b8")
        draw.polygon([(px - 16, beam_y + 25), (px + 16, beam_y + 25), (px, beam_y + 52)], fill="#64748b")
        draw.text((px, beam_y + 65), f"支座{index + 1}", fill="#334155", font=font, anchor="mm")
    for index, length in enumerate(model.spans_m):
        center = (model.boundaries_m[index] + model.boundaries_m[index + 1]) / 2
        draw.text((scale(center), beam_y + 100), f"第{index + 1}跨 L={length:g}m", fill="#334155", font=font, anchor="mm")
    for point in model.point_loads:
        px = scale(point.x_m)
        draw.line((px, 62, px, beam_y - 8), fill="#dc2626", width=2)
        draw.polygon([(px - 5, beam_y - 14), (px + 5, beam_y - 14), (px, beam_y - 5)], fill="#dc2626")
    for index, section in enumerate(result.control_sections):
        px = scale(section.x_m)
        top = 125 - (index % 4) * 21
        draw.line((px, top, px, beam_y + 5), fill="#2563eb", width=1)
        draw.text((px, top - 10), section.section_id, fill="#1d4ed8", font=font, anchor="mm")
    try:
        legend_font = ImageFont.truetype(font_path, 10)
    except OSError:  # pragma: no cover
        legend_font = font
    legend_rows = (len(result.control_sections) + 1) // 2
    for index, section in enumerate(result.control_sections):
        column = index // legend_rows
        row = index % legend_rows
        x = margin + column * (width - 2 * margin) / 2
        y = 305 + row * 13
        draw.text((x, y), f"{section.section_id}｜{section.name}｜x={section.x_m:g}m", fill="#334155", font=legend_font)
    draw.text((width / 2, height - 18), "正弯矩：板底/梁底受拉；负弯矩：板面/梁顶受拉；截面位置来自实际计算提取点", fill="#334155", font=font, anchor="mm")
    output = BytesIO()
    image.save(output, format="PNG")
    return ChartArtifact("".join(svg_parts), output.getvalue(), figure)
