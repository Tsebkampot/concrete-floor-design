"""智能校核和错误提示。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from calculations.section_estimation import estimate_all_sections


@dataclass(frozen=True)
class CheckItem:
    """校核结果。"""

    level: str
    category: str
    item: str
    message: str
    suggestion: str


def check_design_parameters(params: dict, has_results: dict[str, bool] | None = None) -> list[CheckItem]:
    """对统一输入参数、计算结果完整性和构造说明进行校核。"""
    items: list[CheckItem] = []
    has_results = has_results or {}

    def add(level: str, category: str, item: str, message: str, suggestion: str) -> None:
        items.append(CheckItem(level, category, item, message, suggestion))

    for name in ["slab_span_m", "secondary_span_m", "main_span_m"]:
        if params.get(name, 0) <= 0:
            add("错误", "参数合理性", name, "跨度必须大于 0", "返回基本参数页面修正跨度")

    for name in ["fc", "fy_slab", "fy_beam", "fyv"]:
        if params.get(name, 0) <= 0:
            add("错误", "参数合理性", name, "材料强度必须大于 0", "检查材料等级或手动输入强度")

    if params.get("gamma_g", 0) <= 1 or params.get("gamma_q", 0) <= 1:
        add("警告", "荷载分项系数", "分项系数", "分项系数通常应大于 1", "如为课程设计指定值可保留，否则建议复核")

    slab_h = params.get("slab_h_mm", 0)
    if slab_h < 80 or slab_h > 120:
        add("警告", "截面尺寸", "板厚", "板厚不在 80-120 mm 建议范围内", "建议查看截面初估页面并复核构造要求")

    try:
        estimates = estimate_all_sections(
            params.get("slab_h_mm", 0),
            params.get("secondary_span_m", 0),
            params.get("secondary_b_mm", 0),
            params.get("secondary_h_mm", 0),
            params.get("main_span_m", 0),
            params.get("main_b_mm", 0),
            params.get("main_h_mm", 0),
        )
        for estimate in estimates:
            if estimate.judgement != "合理":
                add("警告", "截面尺寸", estimate.member, estimate.judgement, estimate.suggestion)
    except ValueError as exc:
        add("错误", "截面尺寸", "初估", str(exc), "修正跨度和截面尺寸后重新计算")

    for key, label in [("slab", "板"), ("secondary", "次梁"), ("main", "主梁")]:
        if not has_results.get(key, False):
            add("提示", "结果完整性", label, f"{label}尚无当前计算结果", "进入对应页面完成一次计算")

    if not has_results.get("manual_compare", False):
        add("提示", "手算对比", "手算对比", "程序结果不能替代手算复核", "保留测试算例与手算对比模块")

    add("提示", "适用范围", "矩阵刚度法", "正式内力采用线弹性连续梁矩阵刚度法；配筋构造和抗剪仍含课程设计默认值", "按采用规范复核最小配筋、裂缝、挠度、锚固和箍筋")
    return items


def check_rebar_table(rows: list[dict]) -> list[CheckItem]:
    """检查配筋推荐表中的不足和超配情况。"""
    items: list[CheckItem] = []
    for row in rows:
        name = row.get("方案", row.get("配筋方案", "配筋方案"))
        over = float(row.get("超配率 (%)", 0) or 0)
        ok = row.get("是否满足", row.get("判断", "满足"))
        if ok == "不满足" or ok is False:
            items.append(CheckItem("错误", "配筋校核", name, "实配面积小于计算所需面积", "增大直径、根数或减小间距"))
        elif over > 30:
            items.append(CheckItem("警告", "配筋校核", name, "超配率超过 30%，可能偏保守", "结合构造和经济性复核"))
    return items


def checks_to_dataframe(items: list[CheckItem]) -> pd.DataFrame:
    """校核结果转表格。"""
    return pd.DataFrame(
        [[i.level, i.category, i.item, i.message, i.suggestion] for i in items],
        columns=["等级", "类别", "项目", "提示内容", "处理建议"],
    )
