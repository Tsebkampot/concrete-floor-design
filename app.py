"""整体式单向板肋形楼盖设计辅助计算平台。"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculations.checks import check_design_parameters, checks_to_dataframe
from calculations.common import CONCRETE_DESIGN_STRENGTH, STEEL_DESIGN_STRENGTH, default_parameters
from calculations.course_design_method import calculate_course_design_method
from calculations.loads import calculate_load_transfer, transfer_to_dataframe
from calculations.main_beam import MainBeamInput, calculate_main_beam
from calculations.moment_capacity import calculate_moment_capacity
from calculations.secondary_beam import SecondaryBeamInput, calculate_secondary_beam
from calculations.section_estimation import estimate_all_sections, estimates_to_dataframe
from calculations.slab import SlabInput, calculate_slab
from calculations.project_analysis import analyze_project_matrix, member_tables
from calculations.specification_parameters import parameters_table_rows
from charts.plot_moment import figure_to_png_bytes
from charts.plot_control_sections import plot_control_section_diagram
from charts.plot_force_envelope import plot_matrix_moment_envelope, plot_matrix_shear_envelope
from charts.plot_resisting_moment import plot_resisting_moment_diagram
from export.export_excel import build_excel_workbook
from export.export_pdf import build_pdf_report
from export.export_report import build_markdown_report
from export.report_summary import build_calculation_book_tables
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

NAV_GROUPS = [
    (
        "基础设置",
        [
            ("🏠 首页", "🏠 首页"),
            ("⚙️ 基本参数", "⚙️ 基本参数"),
            ("📐 截面初估", "📐 截面初估"),
        ],
    ),
    (
        "构件计算",
        [
            ("🧱 板计算", "🧱 板计算"),
            ("🏗️ 次梁计算", "🏗️ 次梁计算"),
            ("🏛️ 主梁计算", "🏛️ 主梁计算"),
            ("🔁 荷载传递", "🔁 荷载传递"),
        ],
    ),
    (
        "分析与校核",
        [
            ("🧮 配筋推荐", "🧮 配筋推荐"),
            ("📊 图表分析", "📊 图表分析"),
            ("📈 抵抗弯矩", "📈 抵抗弯矩"),
            ("📉 最不利组合", "📈 最不利荷载组合分析"),
            ("✅ 智能校核", "✅ 智能校核"),
        ],
    ),
    (
        "成果输出",
        [
            ("📤 结果导出", "📤 结果导出"),
            ("📄 自动计算书", "📄 自动计算书"),
            ("📘 程序说明", "📘 程序说明"),
        ],
    ),
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
.nav-group-title {
  color: #bfeeff;
  font-size: 12px;
  font-weight: 760;
  letter-spacing: 0;
  margin: 14px 0 5px 0;
  opacity: 0.92;
}
.nav-item-selected {
  display: flex;
  align-items: center;
  min-height: 34px;
  border-radius: 9px;
  padding: 7px 10px;
  margin: 3px 0;
  background: #0ea5b7;
  color: #ffffff;
  border: 1px solid rgba(165, 243, 252, 0.6);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.25;
  box-shadow: 0 8px 18px rgba(14, 165, 183, 0.2);
}
.nav-item-selected .nav-emoji {
  width: 22px;
  display: inline-flex;
  justify-content: center;
  margin-right: 7px;
  font-size: 15px;
  line-height: 1;
}
.nav-item-selected .nav-text {
  font-size: 15px;
}
section[data-testid="stSidebar"] div.stButton {
  margin: 0;
}
section[data-testid="stSidebar"] div.stButton > button {
  width: 100%;
  justify-content: flex-start;
  min-height: 32px;
  padding: 6px 10px;
  border-radius: 9px;
  border: 1px solid transparent;
  background: transparent;
  color: #e8f8ff;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.25;
  box-shadow: none;
}
section[data-testid="stSidebar"] div.stButton > button:hover {
  background: rgba(186, 230, 253, 0.14);
  border-color: rgba(186, 230, 253, 0.26);
  color: #ffffff;
}
section[data-testid="stSidebar"] div.stButton > button p {
  width: 100%;
  text-align: left;
  font-size: 15px;
  line-height: 1.2;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] {
  margin-bottom: 1px;
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
.data-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid #d8e3ec;
  border-radius: 10px;
  background: #ffffff;
  margin: 8px 0 14px 0;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  color: #17324d;
  font-size: 14px;
}
.data-table th {
  background: #0f4c81;
  color: #ffffff;
  font-weight: 700;
  padding: 9px 10px;
  border: 1px solid #d8e3ec;
  text-align: left;
  white-space: nowrap;
}
.data-table td {
  background: #ffffff;
  color: #17324d;
  padding: 8px 10px;
  border: 1px solid #d8e3ec;
  vertical-align: top;
}
.data-table tr:nth-child(even) td {
  background: #f6f8fb;
}
.data-table td.cell-ok {
  background: #dcfce7;
  color: #166534;
  font-weight: 650;
}
.data-table td.cell-warn {
  background: #fff7ed;
  color: #9a3412;
  font-weight: 650;
}
.data-table td.cell-error {
  background: #fee2e2;
  color: #991b1b;
  font-weight: 650;
}
@media (prefers-color-scheme: dark) {
  :root {
    --hydro-blue: #38bdf8;
    --hydro-cyan: #22d3ee;
    --deep-blue: #f8fafc;
    --page-bg: #0f172a;
    --card-border: #475569;
    --muted: #cbd5e1;
    --text-color: #f8fafc;
    --secondary-text-color: #cbd5e1;
    --background-color: #0f172a;
    --secondary-background-color: #1e293b;
  }
  .stApp {
    background: #0f172a;
    color: #f8fafc;
  }
  [data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0f172a 0%, #111827 54%, #0f172a 100%);
  }
  [data-testid="stHeader"] {
    background: rgba(15, 23, 42, 0.88);
  }
  .main .block-container,
  [data-testid="stAppViewContainer"],
  [data-testid="stVerticalBlock"],
  [data-testid="stMarkdownContainer"],
  [data-testid="stCaptionContainer"] {
    color: #f8fafc;
  }
  section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #082f49 0%, #075985 58%, #0f172a 100%) !important;
    border-right: 1px solid rgba(125, 211, 252, 0.36);
  }
  section[data-testid="stSidebar"] *,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] span {
    color: #f8fafc !important;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] label {
    border-radius: 8px;
    padding: 5px 7px;
    border: 1px solid transparent;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: rgba(186, 230, 253, 0.14);
    border-color: rgba(186, 230, 253, 0.28);
  }
  section[data-testid="stSidebar"] [role="radiogroup"] [aria-checked="true"] + div,
  section[data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
    color: #ffffff !important;
  }
  .sidebar-subtitle {
    color: #bae6fd !important;
  }
  .nav-group-title {
    color: #bae6fd !important;
  }
  .nav-item-selected {
    background: #0891b2;
    border-color: #67e8f9;
    color: #ffffff !important;
    box-shadow: 0 8px 18px rgba(34, 211, 238, 0.24);
  }
  section[data-testid="stSidebar"] div.stButton > button {
    background: transparent;
    color: #e0f2fe;
    border-color: transparent;
    box-shadow: none;
  }
  section[data-testid="stSidebar"] div.stButton > button:hover {
    background: rgba(186, 230, 253, 0.16);
    border-color: rgba(186, 230, 253, 0.28);
    color: #ffffff;
    box-shadow: none;
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
    background: #1e293b;
    border-color: #475569;
    box-shadow: 0 12px 26px rgba(0, 0, 0, 0.34);
  }
  [data-testid="stMetric"] {
    background: #1e293b;
    border: 1px solid #475569;
    border-radius: 10px;
    padding: 12px 14px;
  }
  [data-testid="stMetric"] *,
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
    background: #1e293b;
    border-left-color: #22d3ee;
    color: #f8fafc;
    border-top: 1px solid #475569;
    border-right: 1px solid #475569;
    border-bottom: 1px solid #475569;
  }
  .warning-box {
    background: #422d12;
    border-left-color: #f59e0b;
    color: #fffbeb;
    border-top: 1px solid #92400e;
    border-right: 1px solid #92400e;
    border-bottom: 1px solid #92400e;
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
    border-bottom: 1px solid #475569;
    gap: 6px;
  }
  div.stTabs [data-baseweb="tab"],
  div[data-baseweb="tab"] {
    background: #1e293b;
    color: #cbd5e1;
    border: 1px solid #475569;
    border-bottom: 0;
    border-radius: 10px 10px 0 0;
  }
  div.stTabs [aria-selected="true"],
  div[data-baseweb="tab"][aria-selected="true"] {
    background: #0891b2 !important;
    color: #ffffff !important;
    border-color: #67e8f9 !important;
    box-shadow: inset 0 -3px 0 #a5f3fc;
  }
  div[data-testid="stExpander"],
  div[data-testid="stExpander"] details {
    background: #111827 !important;
    border: 1px solid #475569;
    border-radius: 10px;
    color: #f8fafc !important;
  }
  div[data-testid="stExpander"] details summary {
    background: #1e293b !important;
    color: #f8fafc !important;
    border-radius: 10px;
    border-bottom: 1px solid #475569;
  }
  div[data-testid="stExpander"] details summary *,
  div[data-testid="stExpander"] [data-testid="stMarkdownContainer"],
  div[data-testid="stExpander"] label,
  div[data-testid="stExpander"] p,
  div[data-testid="stExpander"] span {
    color: #f8fafc !important;
  }
  div[data-testid="stExpander"] details summary:hover {
    background: #243449 !important;
  }
  [data-testid="stDataFrame"],
  [data-testid="stTable"],
  [data-testid="stDataFrameResizable"],
  [data-testid="stDataFrameGlideDataEditor"],
  div[data-testid="stDataFrame"] div,
  div[data-testid="stDataFrame"] canvas {
    background-color: #111827 !important;
    color: #f8fafc !important;
  }
  div[data-testid="stDataFrame"] {
    border: 1px solid #475569;
    border-radius: 8px;
    overflow: hidden;
  }
  [data-testid="stDataFrame"] [role="grid"],
  [data-testid="stDataFrame"] [role="row"],
  [data-testid="stDataFrame"] [role="columnheader"],
  [data-testid="stDataFrame"] [role="gridcell"] {
    background-color: #111827 !important;
    color: #f8fafc !important;
    border-color: #475569 !important;
  }
  [data-testid="stDataFrame"] [role="columnheader"] {
    background-color: #334155 !important;
    color: #f8fafc !important;
    font-weight: 700;
  }
  [data-testid="stTable"] table,
  div[data-testid="stTable"] table,
  .data-table-wrap,
  table {
    color: #f8fafc !important;
    background: #111827 !important;
    border-collapse: collapse;
  }
  [data-testid="stTable"] thead tr,
  [data-testid="stTable"] th,
  thead tr, th {
    background: #334155 !important;
    color: #f8fafc !important;
    border-color: #475569 !important;
  }
  [data-testid="stTable"] tbody tr,
  [data-testid="stTable"] td,
  tbody tr, td {
    background: #1e293b !important;
    color: #f8fafc !important;
    border-color: #475569 !important;
  }
  [data-testid="stTable"] tbody tr:nth-child(even) td,
  tbody tr:nth-child(even) td {
    background: #111827 !important;
  }
  .dataframe,
  .dataframe th,
  .dataframe td,
  .data-table,
  .data-table th,
  .data-table td {
    color: #f8fafc !important;
    border-color: #475569 !important;
  }
  .dataframe th,
  .data-table th {
    background: #334155 !important;
  }
  .dataframe td,
  .data-table td {
    background: #1e293b !important;
  }
  .data-table tr:nth-child(even) td {
    background: #111827 !important;
  }
  .data-table td.cell-ok {
    background: #14532d !important;
    color: #dcfce7 !important;
  }
  .data-table td.cell-warn {
    background: #78350f !important;
    color: #ffedd5 !important;
  }
  .data-table td.cell-error {
    background: #7f1d1d !important;
    color: #fee2e2 !important;
  }
  [data-baseweb="input"],
  [data-baseweb="select"],
  [data-baseweb="textarea"],
  [data-baseweb="base-input"],
  [data-baseweb="select"] > div,
  [data-baseweb="popover"] ul,
  [data-baseweb="menu"],
  div[data-testid="stNumberInput"] input,
  div[data-testid="stTextInput"] input,
  div[data-testid="stSelectbox"] div,
  div[data-testid="stDateInput"] input {
    background: #111827 !important;
    border-color: #475569 !important;
    color: #f8fafc !important;
  }
  [data-baseweb="input"]:focus-within,
  [data-baseweb="select"]:focus-within,
  div[data-testid="stNumberInput"] input:focus,
  div[data-testid="stTextInput"] input:focus,
  div[data-testid="stDateInput"] input:focus {
    border-color: #67e8f9 !important;
    box-shadow: 0 0 0 1px #67e8f9;
  }
  input,
  textarea,
  [role="combobox"],
  [data-baseweb="select"] span,
  [data-baseweb="menu"] li,
  [data-baseweb="popover"] li {
    color: #f8fafc !important;
  }
  input::placeholder,
  textarea::placeholder {
    color: #cbd5e1 !important;
    opacity: 1;
  }
  [data-baseweb="menu"] li:hover,
  [data-baseweb="popover"] li:hover {
    background: #1e293b !important;
  }
  label,
  .stMarkdown,
  .stCaption,
  p,
  span {
    color: inherit;
  }
  label,
  [data-testid="stWidgetLabel"],
  [data-testid="stCaptionContainer"],
  .stCaption {
    color: #cbd5e1 !important;
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


def invalidate_current_results(state: Any) -> None:
    """计算失败时使当前结果失效；保留历史缓存但禁止作为当前结果导出。"""
    state.current_results = None
    state.current_tables = None
    state.calculation_valid = False


def current_results_are_exportable(state: Any) -> bool:
    return bool(getattr(state, "calculation_valid", False) and getattr(state, "current_results", None) is not None)


def metric_table(rows: list[list[Any]]) -> pd.DataFrame:
    """构造四列表格并统一数值精度。"""
    df = pd.DataFrame(rows, columns=["项目", "公式或来源", "数值", "单位"])
    df["数值"] = df["数值"].map(lambda x: round(float(x), 4) if isinstance(x, (int, float)) else x)
    return df


def format_error_number(value: Any, digits: int = 3) -> str:
    """错误提示中的紧凑数值格式。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if digits == 0:
        return str(int(round(number)))
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def span_input_summary(params: dict[str, Any], text_key: str, fallback_key: str) -> str:
    """返回用户输入的跨度列表；为空时回退到单跨值。"""
    text = str(params.get(text_key, "")).strip()
    if text:
        return text
    return format_error_number(params.get(fallback_key, ""))


def component_failure_context(component: str, params: dict[str, Any]) -> str:
    """为计算失败补充构件、跨度、截面和处理建议。"""
    if component == "板":
        return (
            f"当前参数：板各跨={span_input_summary(params, 'slab_spans_text', 'slab_span_m')} m，"
            f"单跨兼容计算跨度={format_error_number(params['slab_span_m'])} m，"
            f"板厚 h={format_error_number(params['slab_h_mm'], 0)} mm，"
            f"h0={format_error_number(params['slab_h0_mm'], 0)} mm，"
            f"板带宽度={format_error_number(params['strip_width_m'])} m。"
            "建议：增大板厚或有效高度、减小板跨/板带宽度，或按课程要求重新确定板截面后再计算。"
        )
    if component == "次梁":
        return (
            f"当前参数：次梁各跨={span_input_summary(params, 'secondary_spans_text', 'secondary_span_m')} m，"
            f"单跨兼容计算跨度={format_error_number(params['secondary_span_m'])} m，"
            f"截面 b×h={format_error_number(params['secondary_b_mm'], 0)}×{format_error_number(params['secondary_h_mm'], 0)} mm，"
            f"h0={format_error_number(params['secondary_h0_mm'], 0)} mm，"
            f"板厚 hf={format_error_number(params['slab_h_mm'], 0)} mm。"
            "建议：跨度变大后同步增大次梁高度、宽度或有效高度，或调整次梁跨度组合；不要沿用默认小截面给出伪精确结果。"
        )
    if component == "主梁":
        return (
            f"当前参数：主梁各跨={span_input_summary(params, 'main_spans_text', 'main_span_m')} m，"
            f"单跨兼容计算跨度={format_error_number(params['main_span_m'])} m，"
            f"截面 b×h={format_error_number(params['main_b_mm'], 0)}×{format_error_number(params['main_h_mm'], 0)} mm，"
            f"h0={format_error_number(params['main_h0_mm'], 0)} mm，"
            f"板厚 hf={format_error_number(params['slab_h_mm'], 0)} mm。"
            "建议：跨度或集中力增大后同步增大主梁高度、宽度或有效高度，并复核主梁 300×600 口径是否仍适用。"
        )
    return (
        f"当前跨度组合：板={span_input_summary(params, 'slab_spans_text', 'slab_span_m')} m；"
        f"次梁={span_input_summary(params, 'secondary_spans_text', 'secondary_span_m')} m；"
        f"主梁={span_input_summary(params, 'main_spans_text', 'main_span_m')} m；"
        f"L1={format_error_number(params['l1_m'])} m；L2={format_error_number(params['l2_m'])} m。"
        "建议：保持主梁等跨、板各跨总长等于一个主梁跨度、主梁总长等于 L1、次梁总长等于 L2，并检查支承数量等于跨数+1。"
    )


def raise_with_component_context(component: str, exc: ValueError, params: dict[str, Any]) -> None:
    """把底层 ValueError 重新包装为可读的构件级提示。"""
    raise ValueError(f"{component}计算失败：{exc}。{component_failure_context(component, params)}") from exc


def option_label(ok: bool) -> str:
    return "满足" if ok else "不满足"


def calculate_project_results(params: dict[str, Any]) -> dict[str, Any]:
    """根据统一参数完成板、次梁、主梁和荷载传递计算。"""
    gamma_g = params["gamma_g"] * params["importance_factor"]
    gamma_q = params["gamma_q"] * params["importance_factor"]
    try:
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
                fc=params["fc"],
                fy=params["fy_slab"],
                h0_mm=params["slab_h0_mm"],
                section_name="单跨兼容摘要（矩阵刚度法）",
                elastic_modulus_mpa=params.get("elastic_modulus_mpa", 25500.0),
                stiffness_factor=params.get("slab_stiffness_factor", 1.0),
            )
        )
    except ValueError as exc:
        raise_with_component_context("板", exc, params)
    try:
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
                fc=params["fc"],
                fy=params["fy_beam"],
                fyv=params["fyv"],
                h0_mm=params["secondary_h0_mm"],
                section_name="单跨兼容摘要（矩阵刚度法）",
                elastic_modulus_mpa=params.get("elastic_modulus_mpa", 25500.0),
                stiffness_factor=params.get("secondary_stiffness_factor", 1.0),
            )
        )
    except ValueError as exc:
        raise_with_component_context("次梁", exc, params)
    try:
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
                fc=params["fc"],
                fy=params["fy_beam"],
                fyv=params["fyv"],
                h0_mm=params["main_h0_mm"],
                section_name="单跨兼容摘要（矩阵刚度法）",
                elastic_modulus_mpa=params.get("elastic_modulus_mpa", 25500.0),
                stiffness_factor=params.get("main_stiffness_factor", 1.0),
            )
        )
    except ValueError as exc:
        raise_with_component_context("主梁", exc, params)
    transfer = calculate_load_transfer(
        slab.dead_load_standard_kN_m2,
        params["live_load"],
        params["secondary_beam_spacing_m"],
        params["secondary_span_m"],
    )
    try:
        matrix_project = analyze_project_matrix(
            params,
            {
                "dead_load_design_kN_m2": slab.dead_load_design_kN_m2,
                "live_load_design_kN_m2": slab.live_load_design_kN_m2,
            },
        )
    except ValueError as exc:
        raise_with_component_context("矩阵分析", exc, params)
    try:
        course_design = calculate_course_design_method(params)
    except ValueError as exc:
        raise_with_component_context("计算书汇总", exc, params)
    return {"slab": slab, "secondary": secondary, "main": main, "transfer": transfer, "matrix": matrix_project, "course_design": course_design}


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
                ["单跨兼容弯矩 M", "统一矩阵刚度求解器", slab.moment_kN_m, "kN·m"],
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
                ["单跨兼容弯矩 M", "统一矩阵刚度求解器", secondary.moment_kN_m, "kN·m"],
                ["单跨兼容剪力 V", "统一矩阵刚度求解器", secondary.shear_kN, "kN"],
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
                ["单跨兼容弯矩 M", "统一矩阵刚度求解器", main.moment_kN_m, "kN·m"],
                ["单跨兼容剪力 V", "统一矩阵刚度求解器", main.shear_kN, "kN"],
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
        "手算对比附录_旧荷载传递": transfer_to_dataframe(results["transfer"]).assign(
            说明="非矩阵刚度法正式传力结果，仅供传统简化方法手算对比"
        ),
    }
    course_design = results.get("course_design")
    if course_design is not None:
        tables["课程系数法_板内力"] = course_design.slab_forces_df
        tables["课程系数法_次梁内力"] = course_design.secondary_forces_df
        tables["课程系数法_主梁荷载口径"] = course_design.main_load_cases_df
        tables["课程系数法_主梁内力"] = course_design.main_forces_df
        tables["课程系数法_配筋对账"] = course_design.rebar_df
        tables["课程系数法_需复核项"] = course_design.review_df
    matrix_project = results.get("matrix")
    secondary_span_source = max(matrix_project.secondary.model.spans_m) if matrix_project is not None else params["secondary_span_m"]
    main_span_source = max(matrix_project.main.model.spans_m) if matrix_project is not None else params["main_span_m"]
    tables["截面尺寸初估"] = estimates_to_dataframe(
        estimate_all_sections(
            params["slab_h_mm"],
            secondary_span_source,
            params["secondary_b_mm"],
            params["secondary_h_mm"],
            main_span_source,
            params["main_b_mm"],
            params["main_h_mm"],
        )
    )
    checks = check_design_parameters(params, {"slab": True, "secondary": True, "main": True, "manual_compare": True})
    tables["智能校核结果"] = checks_to_dataframe(checks)
    if matrix_project is not None:
        tables["矩阵荷载逐级传递"] = matrix_project.transfer_df
        tables["全局荷载工况连续性"] = matrix_project.global_case_df
        tables["课程近似规范参数"] = pd.DataFrame(parameters_table_rows())
        tables.update(member_tables(matrix_project.slab, matrix_project.slab_design_df))
        tables.update(member_tables(matrix_project.secondary, matrix_project.secondary_design_df))
        tables.update(member_tables(matrix_project.main, matrix_project.main_design_df))
        for legacy_key in [
            "板内力与配筋", "板推荐配筋",
            "次梁荷载", "次梁内力与配筋", "次梁推荐纵筋", "次梁推荐箍筋",
            "主梁荷载", "主梁内力与配筋", "主梁推荐纵筋", "主梁推荐箍筋",
        ]:
            tables.pop(legacy_key, None)
    return tables


def render_dataframe(df: pd.DataFrame) -> None:
    """用 HTML 表格统一渲染，保证深色模式下文字和边框清晰。"""
    header = "".join(f"<th>{escape(str(column))}</th>" for column in df.columns)
    rows = []
    for _, row in df.iterrows():
        cells = []
        for value in row:
            text = str(value)
            cell_class = _table_cell_class(text)
            class_attr = f' class="{cell_class}"' if cell_class else ""
            cells.append(f"<td{class_attr}>{escape(text)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    table_html = f"""
<div class="data-table-wrap">
  <table class="data-table">
    <thead><tr>{header}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
"""
    st.markdown(table_html, unsafe_allow_html=True)


def _table_cell_class(text: str) -> str:
    if "不足" in text or "错误" in text or "不满足" in text:
        return "cell-error"
    if "偏保守" in text or "警告" in text or "需复核" in text:
        return "cell-warn"
    if "满足" in text or "合理" in text:
        return "cell-ok"
    return ""


def render_chart(chart) -> None:
    """优先显示 Plotly 图表，缺少依赖时退回 SVG。"""
    if getattr(chart, "figure", None) is not None:
        try:
            st.plotly_chart(chart.figure, width="stretch")
        except TypeError:
            st.plotly_chart(chart.figure, width="stretch")
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


def render_sidebar_navigation() -> str:
    """渲染分组式侧边栏导航，并返回当前内部页面名称。"""
    if "current_page" not in st.session_state or st.session_state.current_page not in PAGES:
        st.session_state.current_page = PAGES[0]
    current_page = st.session_state.current_page
    st.markdown('<div class="sidebar-nav">', unsafe_allow_html=True)
    for group_name, items in NAV_GROUPS:
        st.markdown(f'<div class="nav-group-title">【{escape(group_name)}】</div>', unsafe_allow_html=True)
        for display_label, page_name in items:
            if current_page == page_name:
                emoji, text = display_label.split(" ", 1)
                st.markdown(
                    f'<div class="nav-item-selected"><span class="nav-emoji">{escape(emoji)}</span><span class="nav-text">{escape(text)}</span></div>',
                    unsafe_allow_html=True,
                )
            elif st.button(display_label, key=f"nav_{page_name}", width="stretch"):
                st.session_state.current_page = page_name
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state.current_page


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


def render_home_dashboard(params: dict[str, Any], tables: dict[str, pd.DataFrame], results: dict[str, Any]) -> None:
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
        "Word 和 PDF 计算书按计算数据汇总表口径输出，完整矩阵明细保留在 Excel。",
        "图表为课程设计辅助示意，可在构件页面或完整 Excel 中查看，最终结果需人工复核。",
    ]
    c1, c2, c3 = st.columns(3)
    home_images = matrix_chart_images(results)
    calculation_book_tables = build_calculation_book_tables(params, tables, results)
    with c1:
        st.download_button(
            "Excel 结果表",
            build_excel_workbook(tables, home_images),
            file_name="整体式单向板肋形楼盖计算结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c2:
        st.download_button(
            "Word 计算书",
            build_word_report("整体式单向板肋形楼盖计算数据汇总表", calculation_book_tables, notes),
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


def render_basic_params(params: dict[str, Any], calculation_error: str | None = None) -> None:
    render_header("基本参数输入", "统一管理楼盖尺寸、材料强度、荷载取值和构件截面尺寸。", ["参数中心", "session_state 共享"])
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["平面与布置", "材料", "荷载", "截面尺寸", "矩阵模型"])
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
        params["elastic_modulus_mpa"] = st.number_input("混凝土弹性模量 E (MPa)", min_value=1.0, value=float(params.get("elastic_modulus_mpa", 25500.0)), step=500.0)
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
        params["secondary_flange_width_mm"] = c2.number_input("次梁翼缘有效宽度 bf' (mm，0=课程近似自动)", min_value=0.0, value=float(params.get("secondary_flange_width_mm", 0.0)), step=50.0)
        params["main_flange_width_mm"] = c3.number_input("主梁翼缘有效宽度 bf' (mm，0=课程近似自动)", min_value=0.0, value=float(params.get("main_flange_width_mm", 0.0)), step=50.0)
        st.caption("bf'=0 时暂按 b+12hf 的课程近似值估算；正式设计需按采用规范、梁间距和跨度复核有效翼缘宽度。")
        render_warning_box("更换楼盖平面尺寸或跨度组合后，请同步复核板厚、梁高和有效高度 h0。跨度增大但仍沿用默认小截面时，程序会明确提示截面不足并停止计算，避免给出伪精确结果。")
    with tab5:
        render_info_box("跨度和支承条件使用英文逗号分隔；支承支持 pin、roller、fixed、free。支承数量必须等于节点数，数量不匹配会明确报错。")
        c1, c2, c3 = st.columns(3)
        with c1:
            params["slab_spans_text"] = st.text_input("板各跨跨度 (m)", value=str(params.get("slab_spans_text", "2,2,2")))
            params["slab_supports_text"] = st.text_input("板节点支承条件", value=str(params.get("slab_supports_text", "pin,pin,pin,pin")))
            params["slab_live_spans_text"] = st.text_input("手动板活载跨号", value=str(params.get("slab_live_spans_text", "1,2,3")), help="仅关闭自动枚举时使用")
            params["slab_stiffness_factor"] = st.number_input("板刚度折减系数", min_value=0.05, value=float(params.get("slab_stiffness_factor", 1.0)), step=0.05)
        with c2:
            params["secondary_spans_text"] = st.text_input("次梁各跨跨度 (m)", value=str(params.get("secondary_spans_text", "6,6,6,6,6")))
            params["secondary_supports_text"] = st.text_input("次梁节点支承条件", value=str(params.get("secondary_supports_text", "pin,pin,pin,pin,pin,pin")))
            params["secondary_live_spans_text"] = st.text_input("手动次梁活载跨号", value=str(params.get("secondary_live_spans_text", "1,2,3,4,5")), help="关闭自动枚举时，用于同一全局工况的次梁活载范围")
            params["secondary_stiffness_factor"] = st.number_input("次梁刚度折减系数", min_value=0.05, value=float(params.get("secondary_stiffness_factor", 1.0)), step=0.05)
        with c3:
            params["main_spans_text"] = st.text_input("主梁各跨跨度 (m)", value=str(params.get("main_spans_text", "6,6,6")))
            params["main_supports_text"] = st.text_input("主梁节点支承条件", value=str(params.get("main_supports_text", "pin,pin,pin,pin")))
            params["main_live_spans_text"] = st.text_input("手动主梁活载跨号", value=str(params.get("main_live_spans_text", "1,2,3")), help="仅关闭自动枚举时使用")
            params["main_point_positions_text"] = st.text_input("主梁集中力全局位置 (m)", value=str(params.get("main_point_positions_text", "")), help="留空时按次梁间距自动生成，例如 2,4,8,10")
            params["secondary_to_main_support_number"] = st.number_input("本次主梁所在次梁支座线编号", min_value=1, max_value=9, value=int(params.get("secondary_to_main_support_number", 3)), step=1, help="选择沿 L2 方向哪一条主梁线；次梁在该交点的矩阵反力传给主梁。")
            params["main_stiffness_factor"] = st.number_input("主梁刚度折减系数", min_value=0.05, value=float(params.get("main_stiffness_factor", 1.0)), step=0.05)
        params["automatic_live_patterns"] = st.toggle("自动枚举全部逐跨活载组合", value=bool(params.get("automatic_live_patterns", True)), help="开启：自动枚举活载；关闭：按手动跨号建立同名全局工况。全跨活载请手动输入全部跨号。")
        st.caption("主梁集中力位置由次梁间距自动生成，集中力数值来自次梁矩阵分析的支座反力。")
    st.session_state.params = params
    st.success("参数已写入 session_state，板、次梁、主梁和导出模块会共用这些值。")
    if calculation_error:
        st.error(f"当前输入参数暂不能完成计算：{calculation_error}")


def render_section_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("结构布置与截面尺寸初估", "按课程设计经验范围快速判断板厚、次梁和主梁截面尺寸。", ["经验初估", "构造复核"])
    render_info_box("梁高经验范围：次梁 h=(1/18-1/12)L，主梁 h=(1/15-1/10)L；梁宽 b=(1/3-1/2)h。")
    render_warning_box("如果修改了 L1/L2 或各跨跨度，请先让板厚、梁高、有效高度 h0 与新跨度匹配；截面承载力不足时，程序会提示具体构件和当前截面参数。")
    with st.expander("截面尺寸初估结果", expanded=True):
        render_dataframe(tables["截面尺寸初估"])
        render_warning_box("截面初估只用于方案阶段，最终尺寸仍需结合内力、配筋、挠度和构造要求复核。")


def render_component_page(name: str, tables: dict[str, pd.DataFrame], results: dict[str, Any], presentation_mode: bool = False) -> None:
    if name.startswith("板"):
        result_key, prefix = "slab", "板"
    elif name.startswith("次梁"):
        result_key, prefix = "secondary", "次梁"
    else:
        result_key, prefix = "main", "主梁"
    load_key = f"{prefix}矩阵荷载表"
    matrix = getattr(results["matrix"], result_key)
    design_df = getattr(results["matrix"], f"{result_key}_design_df")
    max_m = max(matrix.control_df["最大正弯矩 (kN·m)"].max(), abs(matrix.control_df["最大负弯矩 (kN·m)"].min()))
    max_v = max(matrix.control_df["最大正剪力 (kN)"].max(), abs(matrix.control_df["最大负剪力 (kN)"].min()))
    render_header(name, f"{component_intro(result_key)}正式内力采用多跨矩阵刚度法。", ["矩阵刚度法", "逐截面设计"])
    render_info_box(
        "控制截面来自实际矩阵内力提取位置：支座中心弯矩与支座边缘弯矩分别保留、分别设计；"
        "支座中心用于检查最大负弯矩，支座边缘同时用于面内弯矩和剪力控制，不把两者混成一个截面。"
    )
    render_metric_cards(
        [("跨数", len(matrix.model.spans_m), "跨", "连续梁模型"), ("荷载工况", len(matrix.patterns), "个", "逐跨活载枚举"), ("控制截面", len(matrix.control_sections), "个", "编号与图表一致"), ("最大 |M|", round(float(max_m), 3), "kN·m", "内力包络"), ("最大 |V|", round(float(max_v), 3), "kN", "内力包络")],
        columns=5,
    )
    tabs = st.tabs(["输入参数", "计算过程", "结果表格", "图形展示", "校核提示", "导出"])
    with tabs[0]:
        with st.expander("节点与支承条件", expanded=True):
            render_dataframe(matrix.node_df)
        with st.expander("单元与 EI", expanded=True):
            render_dataframe(matrix.element_df)
        with st.expander("活载工况", expanded=not presentation_mode):
            render_dataframe(matrix.load_case_df)
    with tabs[1]:
        with st.expander("荷载计算过程", expanded=True):
            st.latex(r"g_d=\gamma_0\gamma_G g_k,\quad q_d=\gamma_0\gamma_Q q_k")
            render_dataframe(tables[load_key])
        with st.expander("矩阵刚度计算过程", expanded=True):
            st.latex(r"\mathbf{K}\mathbf{d}=\mathbf{F},\qquad \mathbf{f}_e=\mathbf{k}_e\mathbf{d}_e-\mathbf{f}_{eq}")
            render_dataframe(matrix.stiffness_summary_df)
            render_dataframe(matrix.end_force_df if not presentation_mode else matrix.end_force_df.head(16))
        with st.expander("逐截面配筋计算", expanded=not presentation_mode):
            st.latex(r"As=\frac{f_c b x}{f_y},\quad M=f_c b x(h_0-x/2)")
            render_dataframe(design_df)
    with tabs[2]:
        with st.expander("控制截面内力包络", expanded=True):
            render_dataframe(matrix.control_df)
        with st.expander("逐控制截面配筋", expanded=True):
            render_dataframe(design_df)
        with st.expander("支座反力", expanded=False):
            render_dataframe(matrix.reaction_df)
    with tabs[3]:
        fig_control = plot_control_section_diagram(matrix)
        render_chart(fig_control)
        st.download_button("导出控制截面示意图 PNG", figure_to_png_bytes(fig_control), file_name=f"{result_key}_control_sections.png", mime="image/png")
        fig_m = plot_matrix_moment_envelope(matrix)
        render_chart(fig_m)
        st.download_button("导出弯矩包络图 PNG", figure_to_png_bytes(fig_m), file_name=f"{result_key}_moment_envelope.png", mime="image/png")
        fig_v = plot_matrix_shear_envelope(matrix)
        render_chart(fig_v)
        st.download_button("导出剪力包络图 PNG", figure_to_png_bytes(fig_v), file_name=f"{result_key}_shear_envelope.png", mime="image/png")
    with tabs[4]:
        error_count = int((design_df["是否满足"] != "满足").sum())
        if error_count:
            render_warning_box(f"发现 {error_count} 条配筋方案未满足默认筛选条件，应调整截面或人工设计。")
        else:
            st.success("全部控制截面均找到满足默认面积与布置条件的方案。")
        render_warning_box("最小配筋率暂按课程设计默认值 0.2% 处理；锚固、截断、裂缝、挠度和具体规范条文仍需人工复核。")
    with tabs[5]:
        subset = {key: value for key, value in tables.items() if key.startswith(prefix)}
        st.download_button(
            "导出本页 Excel",
            build_excel_workbook(subset),
            file_name=f"{result_key}_result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        render_info_box("完整成果包请前往“📤 结果导出”页面生成。")


def render_transfer_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("荷载自动传递总览", "板与次梁的矩阵支座反力逐级传给下一级构件。", ["矩阵反力", "单位追踪"])
    render_load_path_card()
    render_info_box("矩阵刚度法用于各级内力计算。同一 G、Q、G+Q/逐跨活载工况依次完成板求解；板带反力除以板带宽度得到 kN/m 后逐支承线传给次梁；次梁反力再按实际交点位置以 kN 传给主梁。")
    with st.expander("矩阵反力传递明细", expanded=True):
        render_dataframe(tables["矩阵荷载逐级传递"])
    with st.expander("原始荷载量纲核对", expanded=False):
        render_dataframe(tables["手算对比附录_旧荷载传递"])
        st.caption("本表仅供传统简化手算对比，不是矩阵刚度法正式传力结果。")
    render_warning_box("若发现 m、mm 或 kN/m²、kN/m、kN 混用，请回到基本参数页检查单位。")


def render_envelope_page(results: dict[str, Any]) -> None:
    render_header("矩阵刚度法连续内力包络", "比较全部逐跨活载工况，显示真实分段内力曲线。", ["矩阵刚度法", "非插值"])
    render_section_title("三类构件控制截面示意图")
    for label, key in [("板控制截面示意图", "slab"), ("次梁控制截面示意图（30m方向）", "secondary"), ("主梁控制截面示意图（18m方向）", "main")]:
        with st.expander(label, expanded=True):
            render_chart(plot_control_section_diagram(getattr(results["matrix"], key)))
    member = st.radio("选择构件", ["板", "次梁", "主梁"], horizontal=True, key="matrix_envelope_member")
    matrix = {"板": results["matrix"].slab, "次梁": results["matrix"].secondary, "主梁": results["matrix"].main}[member]
    render_chart(plot_matrix_moment_envelope(matrix))
    render_chart(plot_matrix_shear_envelope(matrix))
    with st.expander("控制截面包络数据", expanded=True):
        render_dataframe(matrix.control_df)
    with st.expander("连续包络采样数据", expanded=False):
        render_dataframe(matrix.envelope_df)


def render_load_combination_page(results: dict[str, Any]) -> None:
    render_header("最不利荷载组合分析", "逐跨枚举活载并为每个工况调用矩阵刚度求解器。", ["矩阵工况", "内力包络"])
    member = st.radio("选择分析构件", ["板", "次梁", "主梁"], horizontal=True, key="load_combination_member_matrix")
    matrix = {"板": results["matrix"].slab, "次梁": results["matrix"].secondary, "主梁": results["matrix"].main}[member]
    rows = []
    for pattern in matrix.patterns:
        case = matrix.cases[pattern.name]
        samples = case.sample(61)
        rows.append({"工况": pattern.name, "活载跨": ",".join(str(i + 1) for i in sorted(pattern.active_live_spans)) or "无", "最大 |M| (kN·m)": max(abs(p.moment_kN_m) for p in samples), "最大 |V| (kN)": max(abs(p.shear_kN) for p in samples), "竖向平衡残差 (kN)": case.vertical_equilibrium_error_kN})
    pattern_df = pd.DataFrame(rows)
    render_dataframe(pattern_df)
    bar_fig = go.Figure()
    bar_fig.add_bar(x=pattern_df["工况"], y=pattern_df["最大 |M| (kN·m)"], name="最大 |M|")
    bar_fig.add_bar(x=pattern_df["工况"], y=pattern_df["最大 |V| (kN)"], name="最大 |V|")
    bar_fig.update_layout(title=f"{member}矩阵工况对比", barmode="group", template="plotly_white", legend={"orientation": "h"})
    st.plotly_chart(bar_fig, width="stretch")
    with st.expander("逐控制截面控制工况", expanded=True):
        render_dataframe(matrix.control_df)


def render_rebar_page(tables: dict[str, pd.DataFrame]) -> None:
    render_header("逐控制截面配筋方案", "每个控制截面按自己的正负弯矩和剪力包络独立设计。", ["逐截面", "超配率"])
    render_info_box("超配率 = (实配面积 - 计算所需面积) / 计算所需面积 × 100%。超过 30% 时提示偏保守。")
    for key in ["板逐控制截面配筋表", "次梁逐控制截面配筋表", "主梁逐控制截面配筋表"]:
        with st.expander(key, expanded=True):
            render_dataframe(tables[key])
            render_warning_box("推荐方案仅用于课程设计辅助筛选，最终配筋仍需检查构造、净距、锚固和教师要求。")


def render_resisting_page(results: dict[str, Any]) -> None:
    render_header("逐控制截面抵抗弯矩核对", "用各截面推荐纵筋承载力覆盖对应矩阵设计弯矩。", ["逐截面", "矩阵内力"])
    member = st.radio("选择构件", ["次梁", "主梁"], horizontal=True, key="resisting_member_matrix")
    key = "secondary" if member == "次梁" else "main"
    design = getattr(results["matrix"], f"{key}_design_df").copy()
    legacy = results[key]
    capacities = []
    judgements = []
    for _, row in design.iterrows():
        area = float(row["实配面积 (mm2)"])
        capacity = calculate_moment_capacity(area, legacy.input.fc, legacy.input.fy, legacy.input.b_mm, legacy.input.h0_mm) if area > 0 else 0.0
        signed = -capacity if row["设计方向"] == "负弯矩" else capacity
        capacities.append(signed)
        judgements.append("满足" if abs(signed) + 1e-9 >= abs(float(row["M (kN·m)"])) else "不足")
    design["抵抗弯矩 Mu (kN·m)"] = capacities
    design["承载力判断"] = judgements
    render_dataframe(design[["截面编号", "截面名称", "x (m)", "设计方向", "M (kN·m)", "推荐纵筋", "抵抗弯矩 Mu (kN·m)", "承载力判断"]])
    chart = plot_resisting_moment_diagram(
        design["x (m)"].astype(float).tolist(),
        design["M (kN·m)"].astype(float).tolist(),
        capacities,
        [f"{row['截面编号']}-{row['设计方向']}" for _, row in design.iterrows()],
        f"{member}逐控制截面抵抗弯矩图",
    )
    render_chart(chart)
    st.download_button("导出逐截面抵抗弯矩图 PNG", figure_to_png_bytes(chart), file_name=f"{key}_resisting_moment.png", mime="image/png")
    render_warning_box("纵筋截断、弯起、锚固长度及支座节点构造仍需按课程采用规范人工确定。")


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


def matrix_chart_images(results: dict[str, Any]) -> dict[str, bytes]:
    """生成 Word/Excel 共用的矩阵计算图形。"""
    images: dict[str, bytes] = {}
    for label, key in [("板", "slab"), ("次梁", "secondary"), ("主梁", "main")]:
        matrix = getattr(results["matrix"], key)
        direction = {"slab": "板计算方向", "secondary": "30m方向", "main": "18m方向"}[key]
        images[f"{label}控制截面示意图（{direction}）"] = figure_to_png_bytes(plot_control_section_diagram(matrix))
        images[f"{label}弯矩包络图"] = figure_to_png_bytes(plot_matrix_moment_envelope(matrix))
        images[f"{label}剪力包络图"] = figure_to_png_bytes(plot_matrix_shear_envelope(matrix))
    return images


def render_export_page(params: dict[str, Any], tables: dict[str, pd.DataFrame], results: dict[str, Any]) -> None:
    render_header("结果导出与半自动计算书", "一键生成课程设计答辩和计算书整理所需成果文件。", ["Excel", "Word", "PNG"])
    notes = [
        "Word、Markdown 和 PDF 计算书按计算数据汇总表口径输出，不再倾倒全部矩阵明细。",
        "完整节点、单元、刚度矩阵、反力和包络采样数据仍保留在 Excel 结果表中。",
        "计算书中小组成员、构件编号、手算页码、教师指定系数和构造详图需人工补充。",
        "梁跨中正弯矩按 T 形截面判断，支座负弯矩按矩形截面；当前规范参数与抗剪公式按课程近似值估算，需人工复核。",
    ]
    render_feature_cards(
        [
            ("Excel 结果表", "包含基本参数、构件计算、荷载传递和校核结果。"),
            ("Word 计算书", "按小组计算数据汇总表格式输出，可继续人工补充。"),
            ("PNG 图表", "各图形页面可单独导出，便于放入 PPT。"),
        ],
        columns=3,
    )
    c1, c2, c3 = st.columns(3)
    images = matrix_chart_images(results)
    calculation_book_tables = build_calculation_book_tables(params, tables, results)
    with c1:
        st.download_button(
            "导出完整 Excel",
            build_excel_workbook(tables, images),
            file_name="整体式单向板肋形楼盖计算结果.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c2:
        st.download_button(
            "导出 Word 半自动计算书",
            build_word_report("整体式单向板肋形楼盖计算数据汇总表", calculation_book_tables, notes),
            file_name="整体式单向板肋形楼盖半自动计算书.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    with c3:
        st.download_button("导出 Markdown 计算书", build_markdown_report("整体式单向板肋形楼盖计算数据汇总表", calculation_book_tables, notes).encode("utf-8"), file_name="整体式单向板肋形楼盖半自动计算书.md")
    render_info_box("Word、Markdown 和 PDF 输出计算数据汇总表；完整矩阵明细和图形仍在 Excel 与各构件页面中保留。")


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
            ("汇总表", "按一级类别、项目、板、次梁、主梁、复核提示整理。"),
            ("复核说明", "保留主梁 300×600 口径、截图原始口径和需人工复核事项。"),
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
        page = render_sidebar_navigation()
        st.divider()
        st.caption("统一参数保存在 session_state，所有页面共享。")
        st.markdown("课程设计版 v1.0  \n数据单位：kN、m、mm")

    try:
        results = calculate_project_results(params)
        tables = build_result_tables(results, params)
        st.session_state.latest_results = results
        st.session_state.latest_tables = tables
        st.session_state.current_results = results
        st.session_state.current_tables = tables
        st.session_state.calculation_valid = True
    except ValueError as exc:
        invalidate_current_results(st.session_state)
        st.error(f"当前输入参数暂不能完成计算：{exc}")
        if st.session_state.get("latest_results") is not None:
            st.warning("已保留上一次成功计算结果，但它不对应当前输入参数；本次不显示结果且所有下载入口已禁用。")
        render_basic_params(params, calculation_error=str(exc))
        return

    if page == "🏠 首页":
        render_home_dashboard(params, tables, results)
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
        render_export_page(params, tables, results)
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
