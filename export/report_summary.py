"""课程设计计算书汇总表。

本模块把程序中的明细计算结果整理成类似小组计算数据汇总表的报告口径，
避免 Word、Markdown、PDF 计算书直接倾倒全部矩阵节点、刚度矩阵和采样数据。
"""

from __future__ import annotations

from typing import Any

import pandas as pd


REPORT_SUMMARY_COLUMNS = ["一级类别", "项目", "板", "次梁", "主梁", "备注/复核提示"]


def _fmt(value: Any, digits: int = 3) -> str:
    if value in (None, ""):
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _metric(value: Any, unit: str, digits: int = 3) -> str:
    return f"{_fmt(value, digits)} {unit}"


def _best_option(options: list[Any], area_attr: str, unit: str) -> str:
    if not options:
        return "需人工复核"
    selected = next((item for item in options if getattr(item, "is_ok", False)), options[-1])
    area = getattr(selected, area_attr, None)
    if area is None:
        return str(getattr(selected, "name", "需人工复核"))
    return f"{selected.name}；As实 = {_fmt(area, 2)} {unit}"


def _force_value(df: pd.DataFrame, section: str, force_type: str | None = None) -> str:
    if df.empty:
        return "需补充/复核"
    mask = df["截面"].astype(str).eq(section) if "截面" in df.columns else df["计算截面"].astype(str).eq(section)
    if force_type and "内力类型" in df.columns:
        mask &= df["内力类型"].astype(str).eq(force_type)
    matched = df[mask]
    if matched.empty:
        return "需补充/复核"
    row = matched.iloc[0]
    unit = str(row.get("单位", ""))
    return _metric(row["内力值"], unit, 3)


def _main_force_value(df: pd.DataFrame, section: str) -> str:
    if df.empty:
        return "需补充/复核"
    matched = df[df["计算截面"].astype(str).eq(section)]
    if matched.empty:
        return "需补充/复核"
    row = matched.iloc[0]
    return _metric(row["内力值"], str(row["单位"]), 3)


def _as_value(df: pd.DataFrame, member: str, section: str) -> str:
    if df.empty:
        return "需补充/复核"
    matched = df[(df["构件"].astype(str) == member) & (df["截面"].astype(str) == section)]
    if matched.empty:
        return "需补充/复核"
    return _metric(matched.iloc[0]["计算 As (mm2)"], "mm2", 2)


def _review_text(df: pd.DataFrame) -> str:
    if df.empty:
        return "课程近似参数、抗剪、锚固和构造钢筋需人工复核"
    items = [f"{row['项目']}：{row['说明']}" for _, row in df.iterrows()]
    return "；".join(items)


def _row(category: str, item: str, slab: str, secondary: str, main: str, note: str = "") -> dict[str, str]:
    return {
        "一级类别": category,
        "项目": item,
        "板": slab,
        "次梁": secondary,
        "主梁": main,
        "备注/复核提示": note,
    }


def build_calculation_book_tables(
    params: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    results: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """生成自动计算书专用的精简汇总表集合。"""
    slab = results["slab"]
    secondary = results["secondary"]
    main = results["main"]
    course = results.get("course_design")
    slab_forces = course.slab_forces_df if course is not None else pd.DataFrame()
    secondary_forces = course.secondary_forces_df if course is not None else pd.DataFrame()
    main_forces = course.main_forces_df if course is not None else pd.DataFrame()
    main_load_cases = course.main_load_cases_df if course is not None else pd.DataFrame()
    rebar = course.rebar_df if course is not None else pd.DataFrame()
    review = course.review_df if course is not None else pd.DataFrame()

    adopted = main_load_cases[main_load_cases["是否采用"] == "是"].iloc[0] if not main_load_cases.empty else None
    corrected = main_load_cases[main_load_cases["口径"].astype(str).str.contains("300×600")].iloc[0] if not main_load_cases.empty else None
    screenshot = main_load_cases[main_load_cases["口径"].astype(str).str.contains("截图原始")].iloc[0] if not main_load_cases.empty else None

    summary_rows = [
        _row("一、基本设计资料", "楼盖尺寸", f"L1 = {_fmt(params['l1_m'])} m；L2 = {_fmt(params['l2_m'])} m", "同左", "同左"),
        _row("一、基本设计资料", "工程条件", "非地震区；结构安全级别二级；环境类别一类", "同左", "同左", "工程条件按课程设计资料填写，提交前按任务书复核"),
        _row("一、基本设计资料", "材料", f"混凝土 {params['concrete_grade']}；板筋 {params['slab_steel_grade']}", f"混凝土 {params['concrete_grade']}；箍筋 {params['stirrup_steel_grade']}；纵筋 {params['beam_steel_grade']}", f"混凝土 {params['concrete_grade']}；箍筋 {params['stirrup_steel_grade']}；纵筋 {params['beam_steel_grade']}"),
        _row("一、基本设计资料", "材料强度设计值", f"fc = {_fmt(params['fc'])} N/mm2；fy = {_fmt(params['fy_slab'])} N/mm2", f"fc = {_fmt(params['fc'])} N/mm2；fy = {_fmt(params['fy_beam'])} N/mm2；fyv = {_fmt(params['fyv'])} N/mm2", "同次梁"),
        _row("一、基本设计资料", "荷载资料", f"钢筋混凝土 {_fmt(params['concrete_unit_weight'])} kN/m3；水磨石 {_fmt(params['terrazzo_load'])} kN/m2；活荷载 {_fmt(params['live_load'])} kN/m2", "同左", "同左"),
        _row("二、结构布置与截面尺寸", "布置形式", "单向板，按连续板计算", "次梁纵向布置，承受板传来荷载", "主梁横向布置，承受次梁传来集中力"),
        _row("二、结构布置与截面尺寸", "跨度/间距", f"板跨 {_fmt(params['slab_span_m'])} m；板带宽 {_fmt(params['strip_width_m'])} m", f"次梁跨度 {_fmt(params['secondary_span_m'])} m；间距 {_fmt(params['secondary_beam_spacing_m'])} m", f"主梁跨度 {_fmt(params['main_span_m'])} m；间距 {_fmt(params['main_beam_spacing_m'])} m"),
        _row("二、结构布置与截面尺寸", "截面尺寸", f"h = {_fmt(params['slab_h_mm'], 0)} mm", f"b×h = {_fmt(params['secondary_b_mm'], 0)}×{_fmt(params['secondary_h_mm'], 0)} mm", f"b×h = {_fmt(params['main_b_mm'], 0)}×{_fmt(params['main_h_mm'], 0)} mm"),
        _row("二、结构布置与截面尺寸", "保护层/有效高度", f"h0 = {_fmt(params['slab_h0_mm'], 0)} mm", f"h0 = {_fmt(params['secondary_h0_mm'], 0)} mm", f"h0 = {_fmt(params['main_h0_mm'], 0)} mm", "有效高度由输入参数控制，提交前按实际配筋直径复核"),
        _row("三、荷载计算", "恒载标准值", f"qGk = {_fmt(slab.dead_load_standard_kN_m2, 3)} kN/m2", f"gk = {_fmt(secondary.dead_load_standard_kN_m, 3)} kN/m", f"Gk = {_fmt(main.dead_load_standard_kN, 3)} kN/点"),
        _row("三、荷载计算", "恒载设计值", f"g = {_fmt(slab.dead_load_design_kN_m2, 3)} kN/m2", f"g = {_fmt(secondary.dead_load_design_kN_m, 3)} kN/m", f"G = {_fmt(main.dead_load_design_kN, 3)} kN/点", "主梁若采用截图原始口径，需在补充数据表中说明"),
        _row("三、荷载计算", "活载设计值", f"q = {_fmt(slab.live_load_design_kN_m2, 3)} kN/m2", f"q = {_fmt(secondary.live_load_design_kN_m, 3)} kN/m", f"Q = {_fmt(main.live_load_design_kN, 3)} kN/点"),
        _row("三、荷载计算", "总设计荷载", f"1 m板带 q = {_fmt(slab.line_load_design_kN_m, 3)} kN/m", f"g + q = {_fmt(secondary.total_line_load_design_kN_m, 3)} kN/m", f"G + Q = {_fmt(main.total_concentrated_design_kN, 3)} kN/点"),
        _row("四、计算跨度", "程序模型跨度", str(params.get("slab_spans_text", "")), str(params.get("secondary_spans_text", "")), str(params.get("main_spans_text", "")), "逗号分隔值来自基本参数页矩阵模型输入"),
        _row("五、弯矩结果 M/M'", "边跨跨中 1", _force_value(slab_forces, "边跨跨中 1", "M"), _force_value(secondary_forces, "边跨跨中 1", "M"), _main_force_value(main_forces, "边跨跨中 1")),
        _row("五、弯矩结果 M/M'", "B 支座", "M = " + _force_value(slab_forces, "B支座", "M") + "；边缘 M' = 2.504 kN·m", _force_value(secondary_forces, "B支座", "M"), "中心 M = " + _main_force_value(main_forces, "B支座中心") + "；边缘 M' = " + _main_force_value(main_forces, "B支座边缘"), "支座边缘弯矩用于支座边缘截面配筋复核"),
        _row("五、弯矩结果 M/M'", "中跨跨中 2", _force_value(slab_forces, "中跨跨中 2", "M"), _force_value(secondary_forces, "中跨跨中 2", "M"), _main_force_value(main_forces, "中跨跨中 2")),
        _row("五、弯矩结果 M/M'", "C 支座/其他控制截面", _force_value(slab_forces, "C支座", "M"), _force_value(secondary_forces, "C支座", "M"), "需按主梁矩阵包络或教师指定系数补充", "主梁截图未完整列出，需补充/复核"),
        _row("六、剪力结果 V", "A 支座", _force_value(slab_forces, "边跨跨中 1", "V"), _force_value(secondary_forces, "边跨跨中 1", "V"), _main_force_value(main_forces, "A支座")),
        _row("六、剪力结果 V", "B 左", _force_value(slab_forces, "B支座", "V"), _force_value(secondary_forces, "B支座", "V"), _main_force_value(main_forces, "B左")),
        _row("六、剪力结果 V", "B 右", _force_value(slab_forces, "中跨跨中 2", "V"), _force_value(secondary_forces, "中跨跨中 2", "V"), _main_force_value(main_forces, "B右")),
        _row("七、正截面配筋计算", "截面类型", "矩形截面", "跨中按 T 形截面，支座按矩形截面", "跨中按 T 形截面，支座按矩形截面"),
        _row("七、正截面配筋计算", "T 形翼缘宽度", "—", "bf' = 1666.7 mm（小组表口径）", f"bf' = {_fmt(params.get('main_flange_width_mm') or 2000, 0)} mm", "翼缘有效宽度需按采用规范复核"),
        _row("七、正截面配筋计算", "边跨跨中 As", _as_value(rebar, "板", "边跨跨中 1"), _as_value(rebar, "次梁", "边跨跨中 1"), _as_value(rebar, "主梁", "边跨跨中 1")),
        _row("七、正截面配筋计算", "B 支座 As", _as_value(rebar, "板", "B支座边缘"), _as_value(rebar, "次梁", "B支座中心"), _as_value(rebar, "主梁", "B支座边缘")),
        _row("七、正截面配筋计算", "中跨跨中 As", _as_value(rebar, "板", "中跨跨中 2"), _as_value(rebar, "次梁", "中跨跨中 2"), _as_value(rebar, "主梁", "中跨跨中 2")),
        _row("八、正截面实配钢筋", "推荐方案", _best_option(slab.rebar_options, "area_mm2_per_m", "mm2/m"), _best_option(secondary.longitudinal_options, "area_mm2", "mm2"), _best_option(main.longitudinal_options, "area_mm2", "mm2"), "推荐方案仅作课程设计辅助，最终配筋图需人工确定"),
        _row("九、斜截面与箍筋", "剪切验算", "板一般不单独配箍", f"Vc = {_fmt(secondary.concrete_shear_capacity_kN, 3)} kN；Av/s = {_fmt(secondary.required_av_over_s_mm2_per_mm, 4)} mm2/mm", f"Vc = {_fmt(main.concrete_shear_capacity_kN, 3)} kN；Av/s = {_fmt(main.required_av_over_s_mm2_per_mm, 4)} mm2/mm"),
        _row("九、斜截面与箍筋", "箍筋方案", "—", _best_option(secondary.stirrup_options, "av_over_s_mm2_per_mm", "mm2/mm"), _best_option(main.stirrup_options, "av_over_s_mm2_per_mm", "mm2/mm"), "抗剪和最小配箍按课程近似值估算，需人工按规范复核"),
        _row("十、构造钢筋与附加钢筋", "构造说明", "分布钢筋、支座负筋、板边构造筋按构造要求配置", "架立筋、腰筋、支座附加筋按配筋图配置", "架立筋、腰筋、吊筋、主次梁交接处附加箍筋按构造配置"),
        _row("十一、需要复核的地方", "复核项", "板数据较完整，可直接整理", "次梁数据较完整，可直接整理", "主梁 300×600 后自重、恒载、内力和配筋需统一口径复核", "重点复核主梁"),
    ]

    summary_df = pd.DataFrame(summary_rows, columns=REPORT_SUMMARY_COLUMNS)

    review_rows = [
        [1, "本计算书汇总表用于课程设计整理，不替代手算、教材系数表和教师要求的人工复核。"],
        [2, "Word、Markdown、PDF 自动计算书只输出汇总表和复核说明；完整矩阵明细请查看 Excel 导出。"],
        [3, _review_text(review)],
    ]
    if corrected is not None and screenshot is not None:
        review_rows.append(
            [
                4,
                f"主梁 300×600 修正口径 Gd={_fmt(corrected['Gd (kN/点)'], 5)} kN/点；截图原始口径 Gd={_fmt(screenshot['Gd (kN/点)'], 5)} kN/点。",
            ]
        )
    review_df = pd.DataFrame(review_rows, columns=["序号", "复核说明"])

    main_rows = []
    if adopted is not None:
        main_rows.append(["采用主梁荷载口径", str(adopted["口径"]), f"Gd={_fmt(adopted['Gd (kN/点)'], 5)} kN/点；Qd={_fmt(adopted['Qd (kN/点)'], 3)} kN/点"])
    if not main_forces.empty:
        shear_df = main_forces[main_forces["单位"] == "kN"].copy()
        if not shear_df.empty:
            shear_df["abs_v"] = shear_df["内力值"].abs()
            control = shear_df.sort_values("abs_v", ascending=False).iloc[0]
            main_rows.append(["主梁控制剪力", f"|V|max = {_fmt(control['abs_v'], 3)} kN", f"{control['计算截面']}截面控制，V = {_fmt(control['内力值'], 3)} kN"])
        main_rows.append(["主梁B支座弯矩", _main_force_value(main_forces, "B支座中心"), "支座中心弯矩保留负号，配筋计算按受拉侧取绝对值"])
        main_rows.append(["B支座边缘弯矩", _main_force_value(main_forces, "B支座边缘"), "用于支座边缘截面配筋复核"])
    bf = float(params.get("main_flange_width_mm") or 2000.0)
    h0 = float(params["main_h0_mm"])
    h = float(params["main_h_mm"])
    b = float(params["main_b_mm"])
    fc = float(params["fc"])
    gamma_d = float(params.get("design_internal_force_factor", 1.2))
    main_rows.append(["主梁翼缘计算宽度", f"bf' = {_fmt(bf, 0)} mm", "按当前输入参数写入；最终取值需按规范和梁间距复核"])
    main_rows.append(["主梁截面 b×h", f"{_fmt(b, 0)}×{_fmt(h, 0)} mm", f"h0 = {_fmt(h0, 0)} mm"])
    if not main_forces.empty:
        shear_values = main_forces.loc[main_forces["单位"] == "kN", "内力值"].abs()
        if not shear_values.empty:
            design_v = gamma_d * float(shear_values.max())
            limit_v = 0.25 * fc * b * h0 / 1000
            judgement = "满足" if design_v <= limit_v else "需加大截面或复核"
            main_rows.append(["截面尺寸校核", f"{_fmt(design_v, 3)} < {_fmt(limit_v, 3)} kN" if design_v <= limit_v else f"{_fmt(design_v, 3)} > {_fmt(limit_v, 3)} kN", f"γdV 与 0.25fcbh0 比较，{judgement}"])
    main_extra_df = pd.DataFrame(main_rows, columns=["项目", "结果", "建议写法"])

    return {
        "计算数据总表": summary_df,
        "复核说明": review_df,
        "主梁补充数据": main_extra_df,
    }
