"""整体式单向板肋形楼盖设计辅助计算平台。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculations.checks import check_design_parameters, checks_to_dataframe
from calculations.common import CONCRETE_DESIGN_STRENGTH, STEEL_DESIGN_STRENGTH, default_parameters
from calculations.envelope import calculate_envelope
from calculations.internal_force import force_points_to_dataframe, line_load_control_points, point_load_control_points
from calculations.load_combination import analyze_load_combinations
from calculations.loads import calculate_load_transfer, transfer_to_dataframe
from calculations.main_beam import MainBeamInput, calculate_main_beam
from calculations.moment_capacity import (
    build_resisting_moment_points,
    calculate_moment_capacity,
    resisting_points_to_dataframe,
)
from calculations.rebar import recommend_longitudinal_rebar
from calculations.secondary_beam import SecondaryBeamInput, calculate_secondary_beam
from calculations.section_estimation import estimate_all_sections, estimates_to_dataframe
from calculations.slab import SlabInput, calculate_slab
from charts.plot_moment import figure_to_png_bytes, plot_envelope_diagram, plot_moment_diagram
from charts.plot_resisting_moment import plot_resisting_moment_diagram
from charts.plot_shear import plot_shear_diagram
from export.export_excel import build_excel_workbook
from export.export_pdf import build_pdf_report
from export.export_report import build_markdown_report
from export.export_word import build_word_report


PAGES = [
    "🏠 首页",
    "⚙️ 基本参数",
    "📐 截面初估",
    "🧱 板计算",
    "🏗️ 次梁计算",
    "🏛️ 主梁计算",
    "🔁 荷载传递",
    "🧮 配筋推荐",
    "📊 图表分析",
    "📈 抵抗弯矩",
    "📈 最不利荷载组合分析",
    "✅ 智能校核",
    "📤 结果导出",
    "📄 自动计算书",
    "📘 程序说明",
]


def load_custom_css() -> None:
    """注入统一的工程蓝界面样式。"""
    st.markdown(
        """
<style>
:root {
  --hydro-blue: #0f4c81;
  --hydro-cyan: #0ea5b7;
  --deep-blue: #0b2f4f;
  --page-bg: #eef4f8;
  --card-border: #d8e3ec;
  --muted: #60758a;
}
.stApp {
  background: linear-gradient(180deg, #e8f2f8 0%, #f6f8fb 48%, #eef4f8 100%);
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0b2f4f 0%, #0f4c81 100%);
}
section[data-testid="stSidebar"] * {
  color: #eef8ff !important;
}
div[data-testid="stSidebarNav"] {display: none;}
.main .block-container {
  padding-top: 1.25rem;
  max-width: 1280px;
}
.hero {
  padding: 28px 32px;
  border-radius: 14px;
  background: linear-gradient(135deg, #0b2f4f 0%, #0f6a9b 58%, #16a3b8 100%);
  color: white;
  box-shadow: 0 18px 38px rgba(15, 76, 129, 0.18);
  margin-bottom: 20px;
}
.hero h1 {
  margin: 0 0 10px 0;
  color: white;
  font-size: 34px;
  letter-spacing: 0;
}
.hero p {
  margin: 0;
  color: #e8f8ff;
  font-size: 16px;
}
.hero-badges {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 18px;
}
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255,255,255,0.16);
  border: 1px solid rgba(255,255,255,0.24);
  color: #fff;
  font-size: 13px;
}
.metric-card, .feature-card, .flow-card, .info-card {
  border: 1px solid var(--card-border);
  background: rgba(255,255,255,0.96);
  border-radius: 12px;
  padding: 16px 18px;
  box-shadow: 0 8px 22px rgba(31, 58, 84, 0.07);
  min-height: 104px;
}
.metric-title {
  color: var(--muted);
  font-size: 13px;
  font-weight: 650;
  margin-bottom: 8px;
}
.metric-value {
  color: var(--hydro-blue);
  font-size: 26px;
  font-weight: 760;
  line-height: 1.1;
}
.metric-unit {
  color: #5d7183;
  font-size: 12px;
  margin-left: 4px;
}
.metric-desc {
  color: #6b7f91;
  font-size: 12px;
  margin-top: 8px;
}
.section-title {
  color: var(--deep-blue);
  font-size: 22px;
  font-weight: 760;
  margin: 24px 0 10px 0;
}
.feature-card h3, .flow-card h3, .info-card h3 {
  color: var(--deep-blue);
  margin: 0 0 8px 0;
  font-size: 16px;
}
.feature-card p, .flow-card p, .info-card p {
  color: var(--muted);
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
}
.flow-card {
  text-align: center;
  min-height: 88px;
}
.hydro-box {
  border-left: 5px solid var(--hydro-cyan);
  background: #f4fbfd;
  border-radius: 10px;
  padding: 12px 14px;
  color: #17324d;
  margin: 10px 0;
}
.warning-box {
  border-left: 5px solid #f59e0b;
  background: #fff8eb;
  border-radius: 10px;
  padding: 12px 14px;
  color: #5b3a08;
  margin: 10px 0;
}
.footer {
  color: #6b7f91;
  font-size: 12px;
  text-align: center;
  padding: 24px 0 8px 0;
}
.sidebar-title {
  font-size: 20px;
  font-weight: 760;
  color: #ffffff;
  margin-bottom: 2px;
}
.sidebar-subtitle {
  color: #cdefff;
  font-size: 12px;
  margin-bottom: 14px;
}
div.stButton > button, div.stDownloadButton > button {
  border-radius: 10px;
  border: 1px solid #0ea5b7;
  background: #0f6a9b;
  color: white;
}
div.stTabs [data-baseweb="tab-list"] {
  gap: 6px;
}
div.stTabs [data-baseweb="tab"] {
  border-radius: 10px 10px 0 0;
  background: #e8f2f8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --hydro-blue: #38bdf8;
    --hydro-cyan: #22d3ee;
    --deep-blue: #e6f6ff;
    --page-bg: #0f172a;
    --card-border: #334155;
    --muted: #cbd5e1;
  }
  .stApp {
    background: linear-gradient(180deg, #0b1220 0%, #111827 52%, #0f172a 100%);
    color: #e5eef8;
  }
  .main .block-container,
  [data-testid="stAppViewContainer"],
  [data-testid="stHeader"] {
    color: #e5eef8;
  }
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #082f49 0%, #075985 58%, #0f172a 100%);
    border-right: 1px solid rgba(125, 211, 252, 0.28);
  }
  section[data-testid="stSidebar"] *,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span {
    color: #f0f9ff !important;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] label {
    border-radius: 8px;
    padding: 3px 6px;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: rgba(186, 230, 253, 0.12);
  }
  .sidebar-subtitle {
    color: #bae6fd !important;
  }
  .hero {
    background: linear-gradient(135deg, #082f49 0%, #075985 56%, #0891b2 100%);
    border: 1px solid rgba(125, 211, 252, 0.26);
    box-shadow: 0 18px 38px rgba(0, 0, 0, 0.36);
  }
  .hero p {
    color: #dff7ff;
  }
  .badge {
    background: rgba(14, 165, 183, 0.22);
    border-color: rgba(125, 211, 252, 0.36);
    color: #f8fafc;
  }
  .metric-card, .feature-card, .flow-card, .info-card {
    background: #172033;
    border-color: #334155;
    box-shadow: 0 12px 26px rgba(0, 0, 0, 0.28);
  }
  .metric-title,
  .metric-desc,
  .feature-card p,
  .flow-card p,
  .info-card p,
  .footer {
    color: #cbd5e1;
  }
  .metric-value,
  .feature-card h3,
  .flow-card h3,
  .info-card h3,
  .section-title {
    color: #f8fafc;
  }
  .metric-unit {
    color: #bae6fd;
  }
  .hydro-box {
    background: #102638;
    border-left-color: #22d3ee;
    color: #e0f2fe;
    border-top: 1px solid #1e3a56;
    border-right: 1px solid #1e3a56;
    border-bottom: 1px solid #1e3a56;
  }
  .warning-box {
    background: #342713;
    border-left-color: #f59e0b;
    color: #fde68a;
    border-top: 1px solid #78350f;
    border-right: 1px solid #78350f;
    border-bottom: 1px solid #78350f;
  }
  div.stButton > button,
  div.stDownloadButton > button {
    background: #0e7490;
    border: 1px solid #67e8f9;
    color: #f8fafc;
    box-shadow: 0 8px 18px rgba(8, 145, 178, 0.22);
  }
  div.stButton > button:hover,
  div.stDownloadButton > button:hover {
    background: #0891b2;
    border-color: #a5f3fc;
    color: #ffffff;
    box-shadow: 0 10px 22px rgba(34, 211, 238, 0.28);
  }
  div.stTabs [data-baseweb="tab-list"] {
    border-bottom: 1px solid #334155;
  }
  div.stTabs [data-baseweb="tab"] {
    background: #172033;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-bottom: 0;
  }
  div.stTabs [aria-selected="true"] {
    background: #0e7490 !important;
    color: #ffffff !important;
    border-color: #67e8f9 !important;
  }
  div[data-testid="stExpander"] {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 10px;
  }
  div[data-testid="stExpander"] details summary {
    background: #172033;
    color: #f8fafc;
    border-radius: 10px;
  }
  div[data-testid="stExpander"] details summary:hover {
    background: #1f2a44;
  }
  [data-testid="stDataFrame"],
  [data-testid="stTable"],
  div[data-testid="stDataFrame"] div,
  div[data-testid="stDataFrame"] canvas {
    background-color: #111827;
    color: #e5eef8;
  }
  div[data-testid="stDataFrame"] {
    border: 1px solid #334155;
    border-radius: 8px;
  }
  table {
    color: #e5eef8;
    background: #111827;
  }
  thead tr, th {
    background: #0f4c81 !important;
    color: #f8fafc !important;
    border-color: #38bdf8 !important;
  }
  tbody tr, td {
    background: #172033 !important;
    color: #e5eef8 !important;
    border-color: #334155 !important;
  }
  tbody tr:nth-child(even) td {
    background: #1f2937 !important;
  }
  [data-baseweb="input"],
  [data-baseweb="select"],
  [data-baseweb="textarea"],
  [data-baseweb="base-input"],
  div[data-testid="stNumberInput"] input,
  div[data-testid="stTextInput"] input {
    background: #111827 !important;
    border-color: #475569 !important;
    color: #f8fafc !important;
  }
  [data-baseweb="input"]:focus-within,
  [data-baseweb="select"]:focus-within,
  div[data-testid="stNumberInput"] input:focus,
  div[data-testid="stTextInput"] input:focus {
    border-color: #67e8f9 !important;
    box-shadow: 0 0 0 1px #67e8f9;
  }
  input,
  textarea,
  [role="combobox"],
  [data-baseweb="select"] span {
    color: #f8fafc !important;
  }
  label,
  .stMarkdown,
  .stCaption,
  p,
  span {
    color: inherit;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def ensure_state() -> dict[str, Any]:
    """初始化并返回统一参数字典。"""
    if "params" not in st.session_state:
        st.session_state.params = default_parameters().to_dict()
    return st.session_state.params


def metric_table(rows: list[list[Any]]) -> pd.DataFrame:
    """构造四列表格并统一数值精度。"""
    df = pd.DataFrame(rows, columns=["项目", "公式或来源", "数值", "单位"])
    df["数值"] = df["数值"].map(lambda x: round(float(x), 4) if isinstance(x, (int, float)) else x)
    return df


def option_label(ok: bool) -> str:
    return "满足" if ok else "不满足"


def calculate_project_results(params: dict[str, Any]) -> dict[str, Any]:
    """根据统一参数完成板、次梁、主梁和荷载传递计算。"""
    gamma_g = params["gamma_g"] * params["importance_factor"]
    gamma_q = params["gamma_q"] * params["importance_factor"]
    slab = calculate_slab(
        SlabInput(
            h_mm=params["slab_h_mm"],
            concrete_unit_weight=params["concrete_unit_weight"],
            terrazzo_load=params["terrazzo_load"],
            plaster_thickness_mm=params["plaster_thickness_mm"],
            plaster_unit_weight=params["plaster_unit_weight"],
            live_load=params["live_load"],
            gamma_g=gamma_g,
            gamma_q=gamma_q,
            strip_width_m=params["strip_width_m"],
            l0_m=params["slab_span_m"],
            alpha=1 / 11,
            fc=params["fc"],
            fy=params["fy_slab"],
            h0_mm=params["slab_h0_mm"],
            section_name="跨中正弯矩 1/11",
        )
    )
    secondary = calculate_secondary_beam(
        SecondaryBeamInput(
            slab_dead_load_kN_m2=slab.dead_load_standard_kN_m2,
            tributary_width_m=params["secondary_beam_spacing_m"],
            b_mm=params["secondary_b_mm"],
            h_mm=params["secondary_h_mm"],
            hf_mm=params["slab_h_mm"],
            concrete_unit_weight=params["concrete_unit_weight"],
            plaster_thickness_mm=params["plaster_thickness_mm"],
            plaster_unit_weight=params["plaster_unit_weight"],
            live_load_kN_m2=params["live_load"],
            gamma_g=gamma_g,
            gamma_q=gamma_q,
            l0_m=params["secondary_span_m"],
            alpha=1 / 11,
            beta=0.5,
            fc=params["fc"],
            fy=params["fy_beam"],
            fyv=params["fyv"],
            h0_mm=params["secondary_h0_mm"],
            section_name="次梁跨中正弯矩 1/11",
        )
    )
    main = calculate_main_beam(
        MainBeamInput(
            secondary_dead_load_kN_m=secondary.dead_load_standard_kN_m,
            secondary_span_m=params["secondary_span_m"],
            secondary_spacing_m=params["secondary_beam_spacing_m"],
            b_mm=params["main_b_mm"],
            h_mm=params["main_h_mm"],
            hf_mm=params["slab_h_mm"],
            concrete_unit_weight=params["concrete_unit_weight"],
            plaster_thickness_mm=params["plaster_thickness_mm"],
            plaster_unit_weight=params["plaster_unit_weight"],
            live_load_kN_m2=params["live_load"],
            gamma_g=gamma_g,
            gamma_q=gamma_q,
            l0_m=params["main_span_m"],
            alpha=0.25,
            beta=0.5,
            fc=params["fc"],
            fy=params["fy_beam"],
            fyv=params["fyv"],
            h0_mm=params["main_h0_mm"],
            section_name="主梁跨中集中荷载 1/4",
        )
    )
    transfer = calculate_load_transfer(
        slab.dead_load_standard_kN_m2,
        params["live_load"],
        params["secondary_beam_spacing_m"],
        params["secondary_span_m"],
    )
    return {"slab": slab, "secondary": secondary, "main": main, "transfer": transfer}


def build_result_tables(results: dict[str, Any], params: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """把当前计算结果整理为导出和展示共用表格。"""
    slab = results["slab"]
    secondary = results["secondary"]
    main = results["main"]
    tables = {
        "基本参数": pd.DataFrame([[k, v] for k, v in params.items()], columns=["参数", "数值"]),
        "板荷载": metric_table(
            [
                ["板自重标准值", "h/1000 × γc", slab.self_weight_kN_m2, "kN/m2"],
                ["水磨石面层荷载", "输入值", params["terrazzo_load"], "kN/m2"],
                ["抹面荷载标准值", "t/1000 × γm", slab.plaster_load_kN_m2, "kN/m2"],
                ["恒载标准值合计", "板自重 + 面层 + 抹面", slab.dead_load_standard_kN_m2, "kN/m2"],
                ["恒载设计值", "γ0 × γG × 恒载标准值", slab.dead_load_design_kN_m2, "kN/m2"],
                ["活载设计值", "γ0 × γQ × 活载标准值", slab.live_load_design_kN_m2, "kN/m2"],
                ["板带线荷载设计值", "(恒载设计值 + 活载设计值) × 板带宽度", slab.line_load_design_kN_m, "kN/m"],
            ]
        ),
        "板内力与配筋": metric_table(
            [
                ["控制截面弯矩 M", "alpha × q × l0^2", slab.moment_kN_m, "kN·m"],
                ["混凝土受压区高度 x", "由 M = fc·b·x·(h0-x/2) 求得", slab.compression_zone_x_mm, "mm"],
                ["所需钢筋面积 As", "As = fc·b·x/fy", slab.required_as_mm2_per_m, "mm2/m"],
            ]
        ),
        "板推荐配筋": pd.DataFrame(
            [
                [i.name, round(i.area_mm2_per_m, 2), option_label(i.is_ok), round(i.over_ratio_percent, 2), i.evaluation]
                for i in slab.rebar_options
            ],
            columns=["配筋方案", "实配面积 (mm2/m)", "是否满足", "超配率 (%)", "评价"],
        ),
        "次梁荷载": metric_table(
            [
                ["板传恒载线荷载", "板恒载 × 次梁间距", secondary.slab_dead_line_load_kN_m, "kN/m"],
                ["次梁自重", "γc × b × (h-hf)", secondary.beam_self_weight_kN_m, "kN/m"],
                ["次梁粉刷", "γm × t × (h-hf) × 2", secondary.beam_plaster_load_kN_m, "kN/m"],
                ["恒载标准值合计", "板传恒载 + 自重 + 粉刷", secondary.dead_load_standard_kN_m, "kN/m"],
                ["恒载设计值", "γ0 × γG × 恒载标准值", secondary.dead_load_design_kN_m, "kN/m"],
                ["活载设计值", "γ0 × γQ × 活载标准值", secondary.live_load_design_kN_m, "kN/m"],
                ["总线荷载设计值", "恒载设计值 + 活载设计值", secondary.total_line_load_design_kN_m, "kN/m"],
            ]
        ),
        "次梁内力与配筋": metric_table(
            [
                ["控制截面弯矩 M", "alpha × q × l0^2", secondary.moment_kN_m, "kN·m"],
                ["控制截面剪力 V", "beta × q × l0", secondary.shear_kN, "kN"],
                ["所需纵筋面积 As", "As = fc·b·x/fy", secondary.required_as_mm2, "mm2"],
                ["混凝土抗剪承载力 Vc", "0.7 × sqrt(fc) × b × h0", secondary.concrete_shear_capacity_kN, "kN"],
                ["所需箍筋 Av/s", "max(V-Vc,0)/(fyv×h0)", secondary.required_av_over_s_mm2_per_mm, "mm2/mm"],
            ]
        ),
        "次梁推荐纵筋": pd.DataFrame(
            [
                [i.name, round(i.area_mm2, 2), option_label(i.is_ok), round(i.over_ratio_percent, 2), i.evaluation]
                for i in secondary.longitudinal_options
            ],
            columns=["配筋方案", "实配面积 (mm2)", "是否满足", "超配率 (%)", "评价"],
        ),
        "次梁推荐箍筋": pd.DataFrame(
            [[i.name, round(i.av_over_s_mm2_per_mm, 4), option_label(i.is_ok), i.evaluation] for i in secondary.stirrup_options],
            columns=["箍筋方案", "实配 Av/s (mm2/mm)", "是否满足", "评价"],
        ),
        "主梁荷载": metric_table(
            [
                ["次梁传来恒载集中力", "次梁恒载 × 次梁跨度", main.secondary_dead_concentrated_kN, "kN"],
                ["主梁自重", "γc × b × (h-hf) × 次梁间距", main.beam_self_weight_kN, "kN"],
                ["主梁粉刷", "γm × t × (h-hf) × 2 × 次梁间距", main.beam_plaster_load_kN, "kN"],
                ["恒载标准值合计", "次梁传恒载 + 自重 + 粉刷", main.dead_load_standard_kN, "kN"],
                ["恒载设计值", "γ0 × γG × 恒载标准值", main.dead_load_design_kN, "kN"],
                ["活载设计值", "γ0 × γQ × 活载标准值", main.live_load_design_kN, "kN"],
                ["总集中荷载设计值", "恒载设计值 + 活载设计值", main.total_concentrated_design_kN, "kN"],
            ]
        ),
        "主梁内力与配筋": metric_table(
            [
                ["控制截面弯矩 M", "alpha × P × l0", main.moment_kN_m, "kN·m"],
                ["控制截面剪力 V", "beta × P", main.shear_kN, "kN"],
                ["所需纵筋面积 As", "As = fc·b·x/fy", main.required_as_mm2, "mm2"],
                ["混凝土抗剪承载力 Vc", "0.7 × sqrt(fc) × b × h0", main.concrete_shear_capacity_kN, "kN"],
                ["所需箍筋 Av/s", "max(V-Vc,0)/(fyv×h0)", main.required_av_over_s_mm2_per_mm, "mm2/mm"],
            ]
        ),
        "主梁推荐纵筋": pd.DataFrame(
            [
                [i.name, round(i.area_mm2, 2), option_label(i.is_ok), round(i.over_ratio_percent, 2), i.evaluation]
                for i in main.longitudinal_options
            ],
            columns=["配筋方案", "实配面积 (mm2)", "是否满足", "超配率 (%)", "评价"],
        ),
        "主梁推荐箍筋": pd.DataFrame(
            [[i.name, round(i.av_over_s_mm2_per_mm, 4), option_label(i.is_ok), i.evaluation] for i in main.stirrup_options],
            columns=["箍筋方案", "实配 Av/s (mm2/mm)", "是否满足", "评价"],
        ),
        "荷载传递总览": transfer_to_dataframe(results["transfer"]),
    }
    tables["截面尺寸初估"] = estimates_to_dataframe(
        estimate_all_sections(
            params["slab_h_mm"],
            params["secondary_span_m"],
            params["secondary_b_mm"],
            params["secondary_h_mm"],
            params["main_span_m"],
            params["main_b_mm"],
            params["main_h_mm"],
        )
    )
    checks = check_design_parameters(params, {"slab": True, "secondary": True, "main": True, "manual_compare": True})
    tables["智能校核结果"] = checks_to_dataframe(checks)
    return tables


def render_dataframe(df: pd.DataFrame) -> None:
    styled = style_dataframe(df)
    try:
        st.dataframe(styled, width="stretch", hide_index=True)
    except TypeError:
        st.dataframe(styled, use_container_width=True, hide_index=True)


def render_chart(chart) -> None:
    """优先显示 Plotly 图表，缺少依赖时退回 SVG。"""
    if getattr(chart, "figure", None) is not None:
        try:
            st.plotly_chart(chart.figure, width="stretch")
        except TypeError:
            st.plotly_chart(chart.figure, use_container_width=True)
    else:
        st.markdown(chart.svg, unsafe_allow_html=True)


def style_dataframe(df: pd.DataFrame):
    """统一表格高亮：满足绿色，不足红色，偏保守橙色。"""
    def color_cell(value: object) -> str:
        text = str(value)
        if "不足" in text or "错误" in text or "不满足" in text:
            return "background-color: #fee2e2; color: #991b1b; font-weight: 650;"
        if "偏保守" in text or "警告" in text or "需复核" in text:
            return "background-color: #fff7ed; color: #9a3412; font-weight: 650;"
        if "满足" in text or "合理" in text:
            return "background-color: #dcfce7; color: #166534; font-weight: 650;"
        return ""

    try:
        return df.style.map(color_cell)
    except AttributeError:
        return df.style.applymap(color_cell)


def render_header(title: str, subtitle: str | None = None, badges: list[str] | None = None) -> None:
    """渲染页面 Hero 标题。"""
    badge_html = "".join(f'<span class="badge">{badge}</span>' for badge in (badges or []))
    st.markdown(
        f"""
<div class="hero">
  <h1>{title}</h1>
  <p>{subtitle or ""}</p>
  <div class="hero-badges">{badge_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_title(title: str) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def render_metric_card(title: str, value: str | float, unit: str = "", desc: str = "") -> str:
    """返回指标卡片 HTML。"""
    if isinstance(value, (int, float)):
        value = f"{value:.3f}"
    return f"""
<div class="metric-card">
  <div class="metric-title">{title}</div>
  <div><span class="metric-value">{value}</span><span class="metric-unit">{unit}</span></div>
  <div class="metric-desc">{desc}</div>
</div>
"""


def render_metric_cards(cards: list[tuple[str, str | float, str, str]], columns: int = 4) -> None:
    """按列渲染多个指标卡片。"""
    cols = st.columns(columns)
    for idx, card in enumerate(cards):
        with cols[idx % columns]:
            st.markdown(render_metric_card(*card), unsafe_allow_html=True)


def render_info_box(text: str) -> None:
    st.markdown(f'<div class="hydro-box">{text}</div>', unsafe_allow_html=True)


def render_warning_box(text: str) -> None:
    st.markdown(f'<div class="warning-box">{text}</div>', unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown('<div class="footer">整体式单向板肋形楼盖设计辅助计算平台 · 课程设计版 v1.0 · 数据单位 kN / m / mm</div>', unsafe_allow_html=True)


def render_feature_cards(items: list[tuple[str, str]], columns: int = 3) -> None:
    cols = st.columns(columns)
    for idx, (title, desc) in enumerate(items):
        with cols[idx % columns]:
            st.markdown(f'<div class="feature-card"><h3>{title}</h3><p>{desc}</p></div>', unsafe_allow_html=True)


def render_flow(items: list[str]) -> None:
    cols = st.columns(len(items))
    for idx, item in enumerate(items):
        with cols[idx]:
            st.markdown(f'<div class="flow-card"><h3>{idx + 1}</h3><p>{item}</p></div>', unsafe_allow_html=True)


def best_option_name(options: list[Any]) -> str:
    """取第一个满足要求的配筋方案名称。"""
    for item in options:
        if getattr(item, "is_ok", False):
            return item.name
    return options[-1].name if options else "需复核"


def component_intro(result_key: str) -> str:
    """构件页答辩讲解词。"""
    return {
        "slab": "本模块根据楼面恒载、活载和板带宽度，计算单向板控制截面弯矩和所需钢筋面积。",
        "secondary": "本模块自动接收板传来的面荷载，并转换为次梁线荷载，完成次梁内力和配筋计算。",
        "main": "本模块自动接收次梁传来的集中荷载，完成主梁控制截面内力与配筋计算。",
    }[result_key]


def component_metric_cards(result_key: str, results: dict[str, Any]) -> list[tuple[str, str | float, str, str]]:
    """构件关键结果卡片。"""
    if result_key == "slab":
        slab = results["slab"]
        return [
            ("恒载标准值 qGk", slab.dead_load_standard_kN_m2, "kN/m2", "板面恒载合计"),
            ("活载标准值 qQk", slab.input.live_load, "kN/m2", "楼面活荷载标准值"),
            ("荷载设计值 q", slab.line_load_design_kN_m, "kN/m", "1 m 板带设计线荷载"),
            ("控制弯矩 M", slab.moment_kN_m, "kN·m", "控制截面弯矩"),
            ("所需钢筋面积 As", slab.required_as_mm2_per_m, "mm2/m", "按简化受弯公式"),
        ]
    if result_key == "secondary":
        beam = results["secondary"]
        return [
            ("板传恒载", beam.slab_dead_line_load_kN_m, "kN/m", "板面恒载 × 次梁间距"),
            ("次梁自重", beam.beam_self_weight_kN_m, "kN/m", "板下梁肋自重"),
            ("总恒载标准值", beam.dead_load_standard_kN_m, "kN/m", "板传恒载 + 自重 + 粉刷"),
            ("最大弯矩", beam.moment_abs_kN_m, "kN·m", "控制截面弯矩绝对值"),
            ("最大剪力", beam.shear_abs_kN, "kN", "控制截面剪力绝对值"),
            ("推荐纵筋", best_option_name(beam.longitudinal_options), "", "首个满足方案"),
        ]
    main = results["main"]
    return [
        ("次梁传来集中力", main.secondary_dead_concentrated_kN, "kN", "次梁恒载线荷载 × 跨度"),
        ("主梁自重", main.beam_self_weight_kN, "kN", "按次梁间距折算集中力"),
        ("总恒载标准值", main.dead_load_standard_kN, "kN", "恒载集中力合计"),
        ("最大弯矩", main.moment_abs_kN_m, "kN·m", "控制截面弯矩绝对值"),
        ("最大剪力", main.shear_abs_kN, "kN", "控制截面剪力绝对值"),
        ("推荐纵筋", best_option_name(main.longitudinal_options), "", "首个满足方案"),
    ]


def check_counts(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    """统计智能校核状态数量。"""
    df = tables.get("智能校核结果", pd.DataFrame())
    if df.empty or "等级" not in df:
        return {"错误": 0, "警告": 0, "提示": 0}
    return {
        "错误": int((df["等级"] == "错误").sum()),
        "警告": int((df["等级"] == "警告").sum()),
        "提示": int((df["等级"] == "提示").sum()),
    }


def input_table_for_component(result_key: str, result: Any) -> pd.DataFrame:
    """把构件输入参数转为中文表格，避免页面显示 dataclass repr。"""
    data = result.input
    common_rows = [
        ["混凝土强度设计值 fc", data.fc, "N/mm2"],
        ["钢筋强度设计值 fy", data.fy, "N/mm2"],
        ["截面有效高度 h0", data.h0_mm, "mm"],
        ["恒载分项系数", data.gamma_g, "-"],
        ["活载分项系数", data.gamma_q, "-"],
        ["计算跨度 l0", data.l0_m, "m"],
        ["弯矩系数 alpha", data.alpha, "-"],
    ]
    if result_key == "slab":
        rows = [
            ["板厚 h", data.h_mm, "mm"],
            ["钢筋混凝土重度", data.concrete_unit_weight, "kN/m3"],
            ["水磨石面层荷载", data.terrazzo_load, "kN/m2"],
            ["石灰砂浆抹面厚度", data.plaster_thickness_mm, "mm"],
            ["石灰砂浆重度", data.plaster_unit_weight, "kN/m3"],
            ["楼面活荷载标准值", data.live_load, "kN/m2"],
            ["板带宽度", data.strip_width_m, "m"],
            *common_rows,
        ]
    elif result_key == "secondary":
        rows = [
            ["板传来的恒载标准值", data.slab_dead_load_kN_m2, "kN/m2"],
            ["次梁承担板带宽度", data.tributary_width_m, "m"],
            ["次梁宽度 b", data.b_mm, "mm"],
            ["次梁高度 h", data.h_mm, "mm"],
            ["板厚 hf", data.hf_mm, "mm"],
            ["钢筋混凝土重度", data.concrete_unit_weight, "kN/m3"],
            ["粉刷厚度", data.plaster_thickness_mm, "mm"],
            ["粉刷重度", data.plaster_unit_weight, "kN/m3"],
            ["楼面活荷载标准值", data.live_load_kN_m2, "kN/m2"],
            ["剪力系数 beta", data.beta, "-"],
            ["箍筋强度设计值 fyv", data.fyv, "N/mm2"],
            *common_rows,
        ]
    else:
        rows = [
            ["次梁传来的恒载标准值", data.secondary_dead_load_kN_m, "kN/m"],
            ["次梁跨度 / 集中力影响长度", data.secondary_span_m, "m"],
            ["次梁间距", data.secondary_spacing_m, "m"],
            ["主梁宽度 b", data.b_mm, "mm"],
            ["主梁高度 h", data.h_mm, "mm"],
            ["板厚 hf", data.hf_mm, "mm"],
            ["钢筋混凝土重度", data.concrete_unit_weight, "kN/m3"],
            ["粉刷厚度", data.plaster_thickness_mm, "mm"],
            ["粉刷重度", data.plaster_unit_weight, "kN/m3"],
            ["楼面活荷载标准值", data.live_load_kN_m2, "kN/m2"],
            ["剪力系数 beta", data.beta, "-"],
            ["箍筋强度设计值 fyv", data.fyv, "N/mm2"],
            *common_rows,
        ]
    df = pd.DataFrame(rows, columns=["参数", "数值", "单位"])
    df["数值"] = df["数值"].map(lambda x: round(float(x), 4) if isinstance(x, (int, float)) else x)
    return df


def split_force_and_rebar_calc(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """将混合的内力与配筋计算表拆成两个展示表。"""
    mask = df["项目"].astype(str).str.contains("弯矩|剪力")
    return df[mask].reset_index(drop=True), df[~mask].reset_index(drop=True)


def graph_note(kind: str, data_source: str, scope: str, review: str) -> None:
    """显示统一图形说明区域。"""
    st.info(
        f"图形类型：{kind}\n\n"
        f"采用数据：{data_source}\n\n"
        f"适用范围：{scope}\n\n"
        f"需人工复核内容：{review}"
    )


def render_load_path_card() -> None:
    """荷载传递路径可视化。"""
    render_section_title("荷载传递路径")
    render_flow(["楼面荷载", "板", "次梁", "主梁", "柱 / 墙"])


def render_completion_overview(tables: dict[str, pd.DataFrame]) -> None:
    """当前计算完成度与校核状态总览。"""
    render_section_title("当前计算完成度")
    steps = ["基本参数", "板计算", "次梁计算", "主梁计算", "图表", "导出"]
    progress = 1.0
    st.progress(progress, text=" / ".join(steps) + " 已就绪")
    counts = check_counts(tables)
    render_metric_cards(
        [
            ("错误数量", counts["错误"], "项", "必须修改"),
            ("警告数量", counts["警告"], "项", "建议复核"),
            ("提示数量", counts["提示"], "项", "可优化说明"),
        ],
        columns=3,
    )


def render_home_dashboard(params: dict[str, Any], tables: dict[str, pd.DataFrame]) -> None:
    """首页平台仪表盘。"""
    render_header(
        "整体式单向板肋形楼盖设计辅助计算平台",
        "面向水工钢筋混凝土课程设计的荷载传递、内力计算、配筋推荐与成果导出工具",
        ["v1.0", "水工钢筋混凝土课程设计", "课程设计版"],
    )
    render_metric_cards(
        [
            ("L1", params["l1_m"], "m", "楼盖平面尺寸"),
            ("L2", params["l2_m"], "m", "楼盖平面尺寸"),
            ("主梁间距", params["main_beam_spacing_m"], "m", "结构布置参数"),
            ("次梁间距", params["secondary_beam_spacing_m"], "m", "板到次梁荷载传递宽度"),
        ],
        columns=4,
    )
    render_section_title("功能模块")
    render_feature_cards(
        [
            ("⚙️ 基本参数输入", "统一管理尺寸、材料、荷载和截面参数。"),
            ("📐 截面尺寸初估", "按课程设计经验范围判断板、次梁、主梁截面。"),
            ("🧱 板计算模块", "完成板荷载、控制弯矩和板筋推荐。"),
            ("🏗️ 次梁计算模块", "自动接收板传荷载，完成次梁内力与配筋。"),
            ("🏛️ 主梁计算模块", "自动接收次梁集中荷载，完成主梁设计辅助计算。"),
            ("🔁 荷载自动传递", "清晰展示 kN/m² → kN/m → kN 的传递路径。"),
            ("🧮 配筋推荐", "输出推荐钢筋方案、是否满足和超配率。"),
            ("📊 图表分析", "展示控制截面弯矩、剪力、包络和抵抗弯矩示意。"),
            ("📤 结果导出", "支持 Excel、Word、Markdown 和 PNG 成果导出。"),
        ],
        columns=3,
    )
    render_section_title("课程设计流程")
    render_flow(["参数输入", "截面初估", "板计算", "次梁计算", "主梁计算", "图表分析", "智能校核", "成果导出"])
    render_section_title("项目亮点")
    render_feature_cards(
        [
            ("覆盖三类构件", "板、次梁、主梁三个模块一体化展示。"),
            ("自动荷载传递", "板到次梁、次梁到主梁的荷载来源清楚可追踪。"),
            ("配筋与超配率", "推荐常用钢筋组合，并提示不足或偏保守。"),
            ("成果导出", "计算表、计算书和图表可直接用于整理答辩材料。"),
            ("答辩展示模式", "隐藏过多输入细节，突出关键结果和讲解逻辑。"),
        ],
        columns=3,
    )
    render_load_path_card()
    render_completion_overview(tables)
    render_section_title("一键生成成果包")
    render_info_box("请进入“📤 结果导出”页面下载 Excel 结果表、Word 计算书；PNG 图表可在各图形页面单独导出。")
    notes = [
        "当前支持 Word/Excel/PNG 导出，PDF 可由 Word 另存为 PDF。",
        "图表为课程设计辅助示意，最终结果需人工复核。",
    ]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "Excel 结果表",
            build_excel_workbook(tables),
            file_name="整体式单向板肋形楼盖计算结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c2:
        st.download_button(
            "Word 计算书",
            build_word_report("整体式单向板肋形楼盖半自动计算书", tables, notes),
            file_name="整体式单向板肋形楼盖半自动计算书.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with c3:
        st.markdown('<div class="info-card"><h3>PNG 图表</h3><p>进入构件或图表页面单独导出。</p></div>', unsafe_allow_html=True)


def select_or_manual(label: str, options: list[float], key: str, params: dict[str, Any]) -> float:
    choice = st.selectbox(label, [*options, "手动输入"], index=options.index(params[key]) if params[key] in options else len(options), key=f"{key}_choice")
    if choice == "手动输入":
        return st.number_input(f"{label}手动值", min_value=0.1, value=float(params[key]), step=0.1, key=f"{key}_manual")
    return float(choice)


def render_basic_params(params: dict[str, Any]) -> None:
    render_header("基本参数输入", "统一管理楼盖尺寸、材料强度、荷载取值和构件截面尺寸。", ["参数中心", "session_state 共享"])
    tab1, tab2, tab3, tab4 = st.tabs(["平面与布置", "材料", "荷载", "截面尺寸"])
    with tab1:
        c1, c2, c3 = st.columns(3)
        with c1:
            params["l1_m"] = select_or_manual("L1 (m)", [18.0, 21.0, 24.0], "l1_m", params)
            params["main_beam_spacing_m"] = st.number_input("主梁间距 (m)", min_value=0.1, value=float(params["main_beam_spacing_m"]), step=0.1)
            params["wall_thickness_mm"] = st.number_input("墙厚 (mm)", min_value=0.0, value=float(params["wall_thickness_mm"]), step=10.0)
        with c2:
            params["l2_m"] = select_or_manual("L2 (m)", [30.0, 36.0], "l2_m", params)
            params["secondary_beam_spacing_m"] = st.number_input("次梁间距 (m)", min_value=0.1, value=float(params["secondary_beam_spacing_m"]), step=0.1)
            params["strip_width_m"] = st.number_input("板带宽度 (m)", min_value=0.1, value=float(params["strip_width_m"]), step=0.1)
        with c3:
            params["slab_bearing_length_mm"] = st.number_input("板搁置长度 (mm)", min_value=0.0, value=float(params["slab_bearing_length_mm"]), step=10.0)
            params["secondary_bearing_length_mm"] = st.number_input("次梁搁置长度 (mm)", min_value=0.0, value=float(params["secondary_bearing_length_mm"]), step=10.0)
            params["main_bearing_length_mm"] = st.number_input("主梁搁置长度 (mm)", min_value=0.0, value=float(params["main_bearing_length_mm"]), step=10.0)
            params["column_b_mm"] = st.number_input("柱截面 b (mm)", min_value=1.0, value=float(params["column_b_mm"]), step=10.0)
            params["column_h_mm"] = st.number_input("柱截面 h (mm)", min_value=1.0, value=float(params["column_h_mm"]), step=10.0)
    with tab2:
        c1, c2, c3, c4 = st.columns(4)
        params["concrete_grade"] = c1.selectbox("混凝土等级", list(CONCRETE_DESIGN_STRENGTH), index=list(CONCRETE_DESIGN_STRENGTH).index(params["concrete_grade"]))
        params["slab_steel_grade"] = c2.selectbox("板中钢筋等级", list(STEEL_DESIGN_STRENGTH), index=list(STEEL_DESIGN_STRENGTH).index(params["slab_steel_grade"]))
        params["stirrup_steel_grade"] = c3.selectbox("梁中箍筋等级", list(STEEL_DESIGN_STRENGTH), index=list(STEEL_DESIGN_STRENGTH).index(params["stirrup_steel_grade"]))
        params["beam_steel_grade"] = c4.selectbox("梁中纵向受力钢筋等级", list(STEEL_DESIGN_STRENGTH), index=list(STEEL_DESIGN_STRENGTH).index(params["beam_steel_grade"]))
        if st.button("按材料等级填入 fc、fy、fyv"):
            params["fc"] = CONCRETE_DESIGN_STRENGTH[params["concrete_grade"]]
            params["fy_slab"] = STEEL_DESIGN_STRENGTH[params["slab_steel_grade"]]
            params["fyv"] = STEEL_DESIGN_STRENGTH[params["stirrup_steel_grade"]]
            params["fy_beam"] = STEEL_DESIGN_STRENGTH[params["beam_steel_grade"]]
        c1, c2, c3, c4 = st.columns(4)
        params["fc"] = c1.number_input("fc (N/mm2)", min_value=0.1, value=float(params["fc"]), step=0.1)
        params["fy_slab"] = c2.number_input("板筋 fy (N/mm2)", min_value=1.0, value=float(params["fy_slab"]), step=10.0)
        params["fy_beam"] = c3.number_input("梁纵筋 fy (N/mm2)", min_value=1.0, value=float(params["fy_beam"]), step=10.0)
        params["fyv"] = c4.number_input("箍筋 fyv (N/mm2)", min_value=1.0, value=float(params["fyv"]), step=10.0)
    with tab3:
        c1, c2, c3 = st.columns(3)
        params["concrete_unit_weight"] = c1.number_input("钢筋混凝土重度 (kN/m3)", min_value=0.1, value=float(params["concrete_unit_weight"]), step=0.1)
        params["terrazzo_load"] = c1.number_input("水磨石面层荷载 (kN/m2)", min_value=0.0, value=float(params["terrazzo_load"]), step=0.01)
        params["plaster_thickness_mm"] = c2.number_input("石灰砂浆抹面厚度 (mm)", min_value=0.0, value=float(params["plaster_thickness_mm"]), step=1.0)
        params["plaster_unit_weight"] = c2.number_input("石灰砂浆重度 (kN/m3)", min_value=0.1, value=float(params["plaster_unit_weight"]), step=0.1)
        params["live_load"] = c3.number_input("楼面活荷载标准值 (kN/m2)", min_value=0.0, value=float(params["live_load"]), step=0.1)
        params["gamma_g"] = c3.number_input("恒载分项系数", min_value=0.1, value=float(params["gamma_g"]), step=0.01)
        params["gamma_q"] = c3.number_input("活载分项系数", min_value=0.1, value=float(params["gamma_q"]), step=0.01)
        params["importance_factor"] = c3.number_input("结构重要性系数 γ0", min_value=0.1, value=float(params["importance_factor"]), step=0.01)
    with tab4:
        c1, c2, c3 = st.columns(3)
        params["slab_h_mm"] = c1.number_input("板厚 h (mm)", min_value=1.0, value=float(params["slab_h_mm"]), step=5.0)
        params["slab_h0_mm"] = c1.number_input("板有效高度 h0 (mm)", min_value=1.0, value=float(params["slab_h0_mm"]), step=5.0)
        params["slab_span_m"] = c1.number_input("板计算跨度 (m)", min_value=0.1, value=float(params["slab_span_m"]), step=0.1)
        params["secondary_b_mm"] = c2.number_input("次梁宽 b (mm)", min_value=1.0, value=float(params["secondary_b_mm"]), step=10.0)
        params["secondary_h_mm"] = c2.number_input("次梁高 h (mm)", min_value=1.0, value=float(params["secondary_h_mm"]), step=10.0)
        params["secondary_h0_mm"] = c2.number_input("次梁有效高度 h0 (mm)", min_value=1.0, value=float(params["secondary_h0_mm"]), step=10.0)
        params["secondary_span_m"] = c2.number_input("次梁计算跨度 (m)", min_value=0.1, value=float(params["secondary_span_m"]), step=0.1)
        params["main_b_mm"] = c3.number_input("主梁宽 b (mm)", min_value=1.0, value=float(params["main_b_mm"]), step=10.0)
        params["main_h_mm"] = c3.number_input("主梁高 h (mm)", min_value=1.0, value=float(params["main_h_mm"]), step=10.0)
        params["main_h0_mm"] = c3.number_input("主梁有效高度 h0 (mm)", min_value=1.0, value=float(params["main_h0_mm"]), step=10.0)
        params["main_span_m"] = c3.number_input("主梁计算跨度 (m)", min_value=0.1, value=float(params["main_span_m"]), step=0.1)
    st.session_state.params = params
    st.success("参数已写入 session_state，板、次梁、主梁和导出模块会共用这些值。")


def render_section_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("结构布置与截面尺寸初估", "按课程设计经验范围快速判断板厚、次梁和主梁截面尺寸。", ["经验初估", "构造复核"])
    render_info_box("梁高经验范围：次梁 h=(1/18-1/12)L，主梁 h=(1/15-1/10)L；梁宽 b=(1/3-1/2)h。")
    with st.expander("截面尺寸初估结果", expanded=True):
        render_dataframe(tables["截面尺寸初估"])
        render_warning_box("截面初估只用于方案阶段，最终尺寸仍需结合内力、配筋、挠度和构造要求复核。")


def render_component_page(name: str, tables: dict[str, pd.DataFrame], results: dict[str, Any], presentation_mode: bool = False) -> None:
    if name.startswith("板"):
        result_key, load_key, design_key, rebar_key = "slab", "板荷载", "板内力与配筋", "板推荐配筋"
        points = line_load_control_points(results["slab"].line_load_design_kN_m, results["slab"].input.l0_m)
        moment_title = "板控制截面弯矩二次插值示意图"
        shear_title = "板简化剪力示意图"
        moment_kind = "quadratic"
        shear_mode = "linear"
    elif name.startswith("次梁"):
        result_key, load_key, design_key, rebar_key = "secondary", "次梁荷载", "次梁内力与配筋", "次梁推荐纵筋"
        points = line_load_control_points(results["secondary"].total_line_load_design_kN_m, results["secondary"].input.l0_m)
        moment_title = "次梁控制截面弯矩二次插值示意图"
        shear_title = "次梁简化剪力示意图"
        moment_kind = "quadratic"
        shear_mode = "linear"
    else:
        result_key, load_key, design_key, rebar_key = "main", "主梁荷载", "主梁内力与配筋", "主梁推荐纵筋"
        points = point_load_control_points(results["main"].total_concentrated_design_kN, results["main"].input.l0_m)
        moment_title = "主梁简化弯矩示意图"
        shear_title = "主梁简化剪力阶梯示意图"
        moment_kind = "control_polyline"
        shear_mode = "step"

    render_header(name, component_intro(result_key), ["答辩展示" if presentation_mode else "计算检查", "课程设计辅助"])
    render_metric_cards(component_metric_cards(result_key, results), columns=3 if result_key != "slab" else 5)

    force_df, rebar_calc_df = split_force_and_rebar_calc(tables[design_key])
    tabs = st.tabs(["输入参数", "计算过程", "结果表格", "图形展示", "校核提示", "导出"])
    with tabs[0]:
        if presentation_mode:
            render_info_box("答辩展示模式已开启：本页优先展示关键参数摘要，完整输入参数可关闭答辩模式后查看。")
            render_dataframe(input_table_for_component(result_key, results[result_key]).head(8))
        else:
            with st.expander("完整输入参数", expanded=True):
                render_dataframe(input_table_for_component(result_key, results[result_key]))
    with tabs[1]:
        with st.expander("荷载计算过程", expanded=True):
            st.latex(r"g_d=\gamma_0\gamma_G g_k,\quad q_d=\gamma_0\gamma_Q q_k")
            render_dataframe(tables[load_key])
            render_warning_box("表中单位已按 kN、m、mm 体系整理；最终计算书仍需人工检查单位换算。")
        with st.expander("内力计算过程", expanded=not presentation_mode):
            st.latex(r"M=\alpha q l_0^2 \quad 或 \quad M=\alpha P l_0")
            if result_key != "slab":
                st.latex(r"V=\beta ql_0 \quad 或 \quad V=\beta P")
            render_dataframe(force_df)
        with st.expander("配筋计算过程", expanded=not presentation_mode):
            st.latex(r"As=\frac{f_c b x}{f_y},\quad M=f_c b x(h_0-x/2)")
            if result_key != "slab":
                st.latex(r"V_c=0.7\sqrt{f_c} b h_0,\quad A_v/s=\frac{\max(V-V_c,0)}{f_{yv}h_0}")
            render_dataframe(rebar_calc_df)
    with tabs[2]:
        st.caption("下列表格汇总程序计算结果，判断结果已按满足、不足、偏保守进行高亮。")
        with st.expander("关键结果表", expanded=True):
            render_dataframe(tables[load_key])
            render_dataframe(force_df)
        with st.expander("配筋推荐表", expanded=True):
            render_dataframe(rebar_calc_df)
            render_dataframe(tables[rebar_key])
            if result_key != "slab":
                render_dataframe(tables["次梁推荐箍筋" if result_key == "secondary" else "主梁推荐箍筋"])
        render_warning_box("配筋推荐用于课程设计辅助筛选，最终钢筋直径、间距、锚固和构造要求需人工复核。")
    with tabs[3]:
        labels = [p.position for p in points]
        xs = [p.x_m for p in points]
        moments = [p.moment_kN_m for p in points]
        shears = [p.shear_kN for p in points]
        with st.expander("控制截面弯矩示意图", expanded=True):
            fig_m = plot_moment_diagram(xs, moments, labels, moment_title, curve_kind=moment_kind)
            render_chart(fig_m)
            st.download_button("导出弯矩图 PNG", figure_to_png_bytes(fig_m), file_name=f"{result_key}_moment.png", mime="image/png")
            st.caption("本图为程序辅助示意图，最终结果需结合课程设计手算过程复核。")
            if result_key in {"slab", "secondary"}:
                graph_note("简化示意 / 控制截面二次插值曲线", "左支座、跨中、右支座控制弯矩", "均布荷载下板或次梁的课程设计展示", "连续梁内力系数、支座条件和手算内力表")
            else:
                graph_note("简化示意 / 控制点分段线", "主梁控制截面弯矩", "主梁受次梁集中力作用且未展开完整集中力位置时的示意展示", "集中力位置、连续梁精确内力和教师指定系数")
        with st.expander("简化剪力示意图", expanded=True):
            fig_v = plot_shear_diagram(xs, shears, labels, shear_title, mode=shear_mode)
            render_chart(fig_v)
            st.download_button("导出剪力图 PNG", figure_to_png_bytes(fig_v), file_name=f"{result_key}_shear.png", mime="image/png")
            st.caption("本图为程序辅助示意图，最终结果需结合课程设计手算过程复核。")
            graph_note("简化示意", "控制截面剪力", "课程设计展示和结果检查", "剪力突变位置、支座反力和斜截面设计")
    with tabs[4]:
        render_warning_box("本模块中的内力系数、抗剪估算和配筋推荐均为课程设计辅助计算，最终应按教材或规范人工复核。")
    with tabs[5]:
        subset = {load_key: tables[load_key], design_key: tables[design_key], rebar_key: tables[rebar_key]}
        st.download_button(
            "导出本页 Excel",
            build_excel_workbook(subset),
            file_name=f"{result_key}_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        render_info_box("完整成果包请前往“📤 结果导出”页面生成。")


def render_transfer_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("荷载自动传递总览", "展示楼面荷载从板传至次梁，再由次梁传至主梁的计算路径。", ["荷载路径", "单位追踪"])
    render_load_path_card()
    render_info_box("板到次梁：kN/m² × m = kN/m；次梁到主梁：kN/m × m = kN。")
    with st.expander("荷载传递明细表", expanded=True):
        render_dataframe(tables["荷载传递总览"])
    render_warning_box("若发现 m、mm 或 kN/m²、kN/m、kN 混用，请回到基本参数页检查单位。")


def render_envelope_page(results: dict[str, Any]) -> None:
    render_header("最不利内力与简化弯矩包络示意图", "比较不同活载布置下的控制截面内力，辅助确定最不利组合。", ["简化包络", "辅助示意"])
    render_warning_box("本模块用于课程设计辅助分析，内力系数和荷载布置应与课程教材或教师要求一致，最终结果需人工复核。")
    member = st.radio("选择构件", ["次梁", "主梁"], horizontal=True)
    if member == "次梁":
        curves, summary = calculate_envelope(results["secondary"].dead_load_design_kN_m, results["secondary"].live_load_design_kN_m, results["secondary"].input.l0_m, "line")
    else:
        curves, summary = calculate_envelope(results["main"].dead_load_design_kN, results["main"].live_load_design_kN, results["main"].input.l0_m, "point")
    rows = []
    section_labels = ["左支座", "跨中", "右支座"]
    for curve in curves:
        for label, x, moment, shear in zip(section_labels, curve.positions, curve.moments, curve.shears):
            rows.append([curve.pattern, label, round(x, 3), round(moment, 4), round(shear, 4)])
    with st.expander("不同活载布置下的控制内力", expanded=True):
        render_dataframe(pd.DataFrame(rows, columns=["活载布置", "截面位置", "x (m)", "弯矩 M (kN·m)", "剪力 V (kN)"]))
    with st.expander("最不利控制内力", expanded=True):
        render_dataframe(summary)
    max_env = [max(curve.moments[i] for curve in curves) for i in range(3)]
    min_env = [min(curve.moments[i] for curve in curves) for i in range(3)]
    st.caption("下图显示多个活载工况控制截面曲线，以及最大包络线和最小包络线。")
    fig = plot_envelope_diagram(curves, max_env, min_env, ["左支座", "跨中", "右支座"], f"{member}简化弯矩包络示意图")
    render_chart(fig)
    st.download_button("导出简化弯矩包络示意图 PNG", figure_to_png_bytes(fig), file_name=f"{member}_envelope.png", mime="image/png")
    st.caption("本图根据左支座、跨中、右支座等控制截面内力绘制，为课程设计辅助示意图，不代表精确连续弯矩曲线，最终结果需结合手算内力表复核。")
    graph_note("简化示意 / 控制点包络", "不同活载布置下的控制截面内力", "课程设计中最不利内力辅助比较", "活载布置、教材内力系数、影响线或教师要求")


def render_load_combination_page(results: dict[str, Any]) -> None:
    render_header("📈 最不利荷载组合分析", "自动比较典型活载布置工况，输出控制弯矩、控制剪力和工程解释。", ["加分项", "活载布置", "包络分析"])
    render_warning_box("本模块采用课程设计辅助简化系数生成典型工况，适合作为答辩展示和最不利内力筛选；最终内力系数仍需按教材或教师要求复核。")
    member = st.radio("选择分析构件", ["板", "次梁", "主梁"], horizontal=True, key="load_combination_member")
    analysis = analyze_load_combinations(member, results)

    render_metric_cards(
        [
            ("最不利工况名称", analysis.controlling_pattern, "", analysis.moment_explanation),
            ("控制弯矩", analysis.controlling_moment, "kN·m", analysis.controlling_layout),
            ("控制剪力", analysis.controlling_shear, "kN", analysis.shear_explanation),
        ],
        columns=3,
    )
    render_info_box(f"{analysis.moment_explanation}；{analysis.shear_explanation}。")

    with st.expander("最不利结果汇总", expanded=True):
        render_dataframe(analysis.summary_df)
    with st.expander("全部工况计算结果", expanded=False):
        render_dataframe(analysis.comparison_df)

    pattern_df = (
        analysis.comparison_df.groupby("工况名称", as_index=False)
        .agg({"弯矩 M (kN·m)": lambda x: x.abs().max(), "剪力 V (kN)": lambda x: x.abs().max()})
        .rename(columns={"弯矩 M (kN·m)": "最大绝对弯矩 (kN·m)", "剪力 V (kN)": "最大绝对剪力 (kN)"})
    )
    bar_fig = go.Figure()
    bar_fig.add_bar(x=pattern_df["工况名称"], y=pattern_df["最大绝对弯矩 (kN·m)"], name="最大绝对弯矩")
    bar_fig.add_bar(x=pattern_df["工况名称"], y=pattern_df["最大绝对剪力 (kN)"], name="最大绝对剪力")
    bar_fig.update_layout(
        title=f"{member}工况对比柱状图",
        barmode="group",
        paper_bgcolor="#f6f8fb",
        plot_bgcolor="#ffffff",
        font={"family": "Arial, Microsoft YaHei, sans-serif", "color": "#17324d"},
        legend={"orientation": "h"},
        margin={"l": 45, "r": 20, "t": 58, "b": 80},
    )
    st.plotly_chart(bar_fig, use_container_width=True)

    labels = analysis.moment_envelope_df["截面位置"].tolist()
    xs = analysis.moment_envelope_df["x (m)"].astype(float).tolist()
    moments = analysis.moment_envelope_df["最大弯矩包络 (kN·m)"].astype(float).tolist()
    shears = analysis.shear_envelope_df["最大剪力包络 (kN)"].astype(float).tolist()
    c1, c2 = st.columns(2)
    with c1:
        render_chart(plot_moment_diagram(xs, moments, labels, f"{member}最大弯矩包络图"))
        with st.expander("最大弯矩包络数据", expanded=False):
            render_dataframe(analysis.moment_envelope_df)
    with c2:
        render_chart(plot_shear_diagram(xs, shears, labels, f"{member}最大剪力包络图"))
        with st.expander("最大剪力包络数据", expanded=False):
            render_dataframe(analysis.shear_envelope_df)


def render_rebar_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("配筋方案推荐与超配率提示", "汇总板筋、梁纵筋和箍筋推荐方案，快速识别不足和偏保守配置。", ["配筋推荐", "超配率"])
    render_info_box("超配率 = (实配面积 - 计算所需面积) / 计算所需面积 × 100%。超过 30% 时提示偏保守。")
    for key in ["板推荐配筋", "次梁推荐纵筋", "次梁推荐箍筋", "主梁推荐纵筋", "主梁推荐箍筋"]:
        with st.expander(key, expanded=key in {"板推荐配筋", "次梁推荐纵筋", "主梁推荐纵筋"}):
            render_dataframe(tables[key])
            render_warning_box("推荐方案仅用于课程设计辅助筛选，最终配筋仍需检查构造、净距、锚固和教师要求。")


def first_ok_longitudinal(options) -> Any:
    for item in options:
        if item.is_ok:
            return item
    return options[-1]


def render_resisting_page(results: dict[str, Any]) -> None:
    render_header("简化抵抗弯矩示意图", "根据推荐纵筋承载力与设计弯矩进行分段示意对比。", ["承载力示意", "人工复核"])
    render_warning_box("简化抵抗弯矩示意图仅用于辅助展示，纵筋截断、弯起、锚固长度应按教材或规范要求人工复核。")
    member = st.radio("选择构件", ["次梁", "主梁"], horizontal=True, key="resisting_member")
    result = results["secondary"] if member == "次梁" else results["main"]
    positive_option = first_ok_longitudinal(result.longitudinal_options)
    negative_option = first_ok_longitudinal(recommend_longitudinal_rebar(result.required_as_mm2 * 1.05))
    positive_mu = calculate_moment_capacity(positive_option.area_mm2, result.input.fc, result.input.fy, result.input.b_mm, result.input.h0_mm)
    negative_mu = calculate_moment_capacity(negative_option.area_mm2, result.input.fc, result.input.fy, result.input.b_mm, result.input.h0_mm)
    points = build_resisting_moment_points(result.input.l0_m, abs(result.moment_kN_m), -abs(result.moment_kN_m) * 0.85, positive_mu, negative_mu)
    df = resisting_points_to_dataframe(points)
    with st.expander("抵抗弯矩控制表", expanded=True):
        render_dataframe(df)
    fig = plot_resisting_moment_diagram(
        [p.x_m for p in points],
        [p.design_moment_kN_m for p in points],
        [p.capacity_kN_m for p in points],
        [p.position for p in points],
        f"{member}简化抵抗弯矩示意图",
    )
    render_chart(fig)
    st.download_button("导出简化抵抗弯矩示意图 PNG", figure_to_png_bytes(fig), file_name=f"{member}_resisting_moment.png", mime="image/png")
    st.caption("纵筋截断、弯起和锚固长度需按教材或规范人工确定。")
    graph_note("简化示意 / 分段抵抗弯矩", "推荐纵筋承载力和控制截面设计弯矩", "展示配筋区段承载力是否覆盖控制弯矩", "纵筋截断、弯起、锚固长度、构造钢筋和详图")


def render_checks_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("智能校核与错误提示", "集中展示参数合理性、结果完整性和人工复核提示。", ["错误", "警告", "提示"])
    df = tables["智能校核结果"]
    counts = check_counts(tables)
    render_metric_cards([("错误", counts["错误"], "项", "必须修改"), ("警告", counts["警告"], "项", "建议复核"), ("提示", counts["提示"], "项", "可优化说明")], columns=3)
    for _, row in df.iterrows():
        text = f"{row['类别']} / {row['项目']}：{row['提示内容']}。{row['处理建议']}"
        if row["等级"] == "错误":
            st.error(text)
        elif row["等级"] == "警告":
            st.warning(text)
        else:
            st.info(text)
    with st.expander("完整校核表", expanded=True):
        render_dataframe(df)


def render_export_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("结果导出与半自动计算书", "一键生成课程设计答辩和计算书整理所需成果文件。", ["Excel", "Word", "PNG"])
    notes = [
        "当前支持 Word/Excel/PNG 导出，PDF 可由 Word 另存为 PDF。",
        "最不利内力包络、斜截面箍筋和简化抵抗弯矩示意图为简化方法，需人工复核。",
        "计算书中小组成员、构件编号、手算页码和教师指定系数需人工补充。",
    ]
    render_feature_cards(
        [
            ("Excel 结果表", "包含基本参数、构件计算、荷载传递和校核结果。"),
            ("Word 计算书", "半自动生成课程设计计算书框架，可继续人工补充。"),
            ("PNG 图表", "各图形页面可单独导出，便于放入 PPT。"),
        ],
        columns=3,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "导出完整 Excel",
            build_excel_workbook(tables),
            file_name="整体式单向板肋形楼盖计算结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c2:
        st.download_button(
            "导出 Word 半自动计算书",
            build_word_report("整体式单向板肋形楼盖半自动计算书", tables, notes),
            file_name="整体式单向板肋形楼盖半自动计算书.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with c3:
        st.download_button("导出 Markdown 计算书", build_markdown_report("整体式单向板肋形楼盖半自动计算书", tables, notes).encode("utf-8"), file_name="整体式单向板肋形楼盖半自动计算书.md")
    render_info_box("图片导出请进入板、次梁、主梁、简化包络示意图或简化抵抗弯矩示意图页面，点击对应 PNG 下载按钮。")


def render_auto_report_page(params: dict[str, Any], tables: dict[str, pd.DataFrame], results: dict[str, Any]) -> None:
    render_header("📄 自动生成计算书", "输入基本学生信息后，自动生成可下载的课程设计计算书 PDF。", ["PDF", "reportlab", "浏览器下载"])
    render_warning_box("PDF 由程序在内存中生成，不保存到本地固定路径；下载位置由浏览器决定。提交前请人工复核计算书中的公式、单位、配筋和教师指定格式。")
    c1, c2 = st.columns(2)
    with c1:
        project_name = st.text_input("项目名称", value="整体式单向板肋形楼盖课程设计计算书")
        student_name = st.text_input("学生姓名", value="")
        student_id = st.text_input("学号", value="")
    with c2:
        class_name = st.text_input("班级", value="")
        report_date = st.date_input("日期")
    render_feature_cards(
        [
            ("封面信息", "项目名称、学生姓名、学号、班级和日期。"),
            ("计算过程", "包含板、次梁、主梁的荷载、内力和配筋表。"),
            ("图表插入", "自动插入弯矩图、剪力图、包络图和抵抗弯矩图。"),
        ],
        columns=3,
    )
    student_info = {
        "project_name": project_name,
        "student_name": student_name,
        "student_id": student_id,
        "class_name": class_name,
        "date": report_date.isoformat(),
    }
    pdf_bytes = build_pdf_report(student_info, params, tables, results)
    st.download_button(
        "下载计算书 PDF",
        pdf_bytes,
        file_name="整体式单向板肋形楼盖课程设计计算书.pdf",
        mime="application/pdf",
    )


def render_markdown_doc(path: str) -> None:
    doc_path = Path(path)
    if doc_path.exists():
        st.markdown(doc_path.read_text(encoding="utf-8"))
    else:
        st.warning(f"未找到文档：{path}")


def main() -> None:
    st.set_page_config(page_title="整体式单向板肋形楼盖设计辅助计算平台", layout="wide")
    load_custom_css()
    params = ensure_state()
    with st.sidebar:
        st.markdown('<div class="sidebar-title">楼盖设计辅助平台</div><div class="sidebar-subtitle">水工钢筋混凝土课程设计</div>', unsafe_allow_html=True)
        presentation_mode = st.toggle("答辩展示模式", value=False, help="开启后隐藏过多输入细节，优先展示关键结果和讲解词。")
        page = st.radio("导航栏", PAGES)
        st.divider()
        st.caption("统一参数保存在 session_state，所有页面共享。")
        st.markdown("课程设计版 v1.0  \n数据单位：kN、m、mm")

    try:
        results = calculate_project_results(params)
        tables = build_result_tables(results, params)
        st.session_state.latest_results = results
        st.session_state.latest_tables = tables
    except ValueError as exc:
        results = st.session_state.get("latest_results")
        tables = st.session_state.get("latest_tables")
        st.error(f"当前输入参数暂不能完成计算：{exc}")
        if results is None or tables is None:
            render_basic_params(params)
            return

    if page == "🏠 首页":
        render_home_dashboard(params, tables)
    elif page == "⚙️ 基本参数":
        render_basic_params(params)
    elif page == "📐 截面初估":
        render_section_page(tables)
    elif page == "🧱 板计算":
        render_component_page("板计算模块", tables, results, presentation_mode)
    elif page == "🏗️ 次梁计算":
        render_component_page("次梁计算模块", tables, results, presentation_mode)
    elif page == "🏛️ 主梁计算":
        render_component_page("主梁计算模块", tables, results, presentation_mode)
    elif page == "🔁 荷载传递":
        render_transfer_page(tables)
    elif page == "📊 图表分析":
        render_envelope_page(results)
    elif page == "🧮 配筋推荐":
        render_rebar_page(tables)
    elif page == "📈 抵抗弯矩":
        render_resisting_page(results)
    elif page == "📈 最不利荷载组合分析":
        render_load_combination_page(results)
    elif page == "✅ 智能校核":
        render_checks_page(tables)
    elif page == "📤 结果导出":
        render_export_page(tables)
    elif page == "📄 自动计算书":
        render_auto_report_page(params, tables, results)
    else:
        render_header("程序说明与已知不足", "说明程序公式、适用范围、简化假定和后续改进方向。", ["说明文档", "人工复核"])
        render_markdown_doc("docs/程序说明书.md")
        st.divider()
        render_markdown_doc("docs/公式与适用范围.md")
        st.divider()
        render_markdown_doc("docs/已知不足与后续改进.md")
    render_footer()


if __name__ == "__main__":
    main()
