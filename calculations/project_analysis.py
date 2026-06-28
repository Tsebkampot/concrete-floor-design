"""板—次梁—主梁矩阵分析与反力传递总流程。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from calculations.force_envelope import MemberEnvelopeResult, analyze_member_envelope, build_member_envelope_from_cases
from calculations.load_cases import LoadPattern
from calculations.matrix_stiffness import elastic_flexural_rigidity_kN_m2
from calculations.section_design import design_control_sections
from calculations.structural_models import (
    ContinuousMemberModel,
    MemberPointLoad,
    analyze_member,
)


@dataclass
class ProjectMatrixResult:
    slab: MemberEnvelopeResult
    secondary: MemberEnvelopeResult
    main: MemberEnvelopeResult
    slab_design_df: pd.DataFrame
    secondary_design_df: pd.DataFrame
    main_design_df: pd.DataFrame
    transfer_df: pd.DataFrame
    global_case_df: pd.DataFrame
    secondary_lines: dict[int, MemberEnvelopeResult]


def parse_number_list(value: str, fallback: float, name: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item.strip()) for item in value.replace("，", ",").split(",") if item.strip())
    except ValueError as exc:
        raise ValueError(f"{name}应使用逗号分隔的数字，例如 2,2,2") from exc
    if not values:
        values = (float(fallback),)
    if len(values) > 8:
        raise ValueError(f"{name}最多输入 8 跨")
    if any(item <= 0 for item in values):
        raise ValueError(f"{name}中的跨度必须大于 0")
    return values


def parse_supports(value: str, span_count: int, name: str) -> tuple[str, ...]:
    aliases = {"铰": "pin", "铰支": "pin", "pin": "pin", "roller": "roller", "fixed": "fixed", "固结": "fixed", "free": "free", "自由": "free"}
    raw = [item.strip().lower() for item in value.replace("，", ",").split(",") if item.strip()]
    if len(raw) != span_count + 1:
        raise ValueError(f"{name}数量应为 {span_count + 1} 个（节点数），当前为 {len(raw)} 个；不允许自动改成全部 pin")
    try:
        return tuple(aliases[item] for item in raw)
    except KeyError as exc:
        raise ValueError(f"{name}仅支持 pin、roller、fixed、free") from exc


def parse_span_selection(value: str, span_count: int, name: str) -> set[int]:
    if not value.strip():
        return set(range(span_count))
    try:
        selected = {int(item.strip()) - 1 for item in value.replace("，", ",").split(",") if item.strip()}
    except ValueError as exc:
        raise ValueError(f"{name}应输入逗号分隔的跨号，例如 1,3") from exc
    if any(index < 0 or index >= span_count for index in selected):
        raise ValueError(f"{name}中的跨号超出 1～{span_count}")
    return selected


def _support_widths(params: dict, member: str, count: int) -> tuple[float, ...]:
    if member == "slab":
        edge = 2 * params["slab_bearing_length_mm"] / 1000
        interior = params["secondary_b_mm"] / 1000
    elif member == "secondary":
        edge = 2 * params["secondary_bearing_length_mm"] / 1000
        interior = params["main_b_mm"] / 1000
    else:
        edge = 2 * params["main_bearing_length_mm"] / 1000
        interior = params["column_b_mm"] / 1000
    return tuple([edge, *([interior] * (count - 1)), edge])


def slab_support_line_reactions(
    slab_model: ContinuousMemberModel,
    case_result,
    strip_width_m: float,
) -> tuple[float, ...]:
    """把板带支座反力 kN 换算为板支承线单位线反力 kN/m。"""
    if strip_width_m <= 0:
        raise ValueError("板带宽度必须大于 0")
    nodes_by_x = {round(node.x_m, 9): node for node in case_result.nodes}
    values = tuple(case_result.node_reaction(nodes_by_x[round(x, 9)].node_id)[0] for x in slab_model.boundaries_m)
    return tuple(value / strip_width_m for value in values)


def _all_support_line_reactions(model: ContinuousMemberModel, case_result) -> tuple[float, ...]:
    nodes_by_x = {round(node.x_m, 9): node for node in case_result.nodes}
    return tuple(case_result.node_reaction(nodes_by_x[round(x, 9)].node_id)[0] for x in model.boundaries_m)


def _validate_regular_layout(params: dict, slab_spans: tuple[float, ...], secondary_spans: tuple[float, ...], main_spans: tuple[float, ...]) -> None:
    """当前逐线映射只接受规则楼盖；避免对不规则布置给出伪精确结果。"""
    tol = 1e-6
    if any(abs(length - main_spans[0]) > tol for length in main_spans):
        raise ValueError("当前逐支座传力仅支持规则等跨主梁楼盖，需人工复核不规则布置")
    if abs(sum(slab_spans) - main_spans[0]) > tol:
        raise ValueError("板各跨总长必须等于一个主梁跨度；当前仅支持规则等跨楼盖")
    if abs(sum(main_spans) - float(params["l1_m"])) > tol:
        raise ValueError("主梁各跨总长必须与 L1 一致，请统一跨度数据源")
    if abs(sum(secondary_spans) - float(params["l2_m"])) > tol:
        raise ValueError("次梁各跨总长必须与 L2 一致，请统一跨度数据源")


def analyze_project_matrix(params: dict, slab_loads: dict[str, float]) -> ProjectMatrixResult:
    """按同一全局工况完成板→次梁支承线→主梁交点的逐级矩阵分析。"""
    automatic = bool(params.get("automatic_live_patterns", True))
    slab_spans = parse_number_list(params.get("slab_spans_text", ""), params["slab_span_m"], "板跨度")
    secondary_spans = parse_number_list(params.get("secondary_spans_text", ""), params["secondary_span_m"], "次梁跨度")
    main_spans = parse_number_list(params.get("main_spans_text", ""), params["main_span_m"], "主梁跨度")
    _validate_regular_layout(params, slab_spans, secondary_spans, main_spans)
    e = float(params.get("elastic_modulus_mpa", 25500.0))
    strip_width = float(params["strip_width_m"])

    slab_model = ContinuousMemberModel(
        "板", slab_spans,
        elastic_flexural_rigidity_kN_m2(e, strip_width * 1000, params["slab_h_mm"], params.get("slab_stiffness_factor", 1.0)),
        tuple(slab_loads["dead_load_design_kN_m2"] * strip_width for _ in slab_spans),
        tuple(slab_loads["live_load_design_kN_m2"] * strip_width for _ in slab_spans),
        _support_widths(params, "slab", len(slab_spans)),
        parse_supports(params.get("slab_supports_text", ""), len(slab_spans), "板支承条件"),
        direction_name="板计算方向",
    )
    slab_result = analyze_member_envelope(
        slab_model, automatic,
        parse_span_selection(params.get("slab_live_spans_text", ""), len(slab_spans), "板活载跨"),
    )
    design_patterns = slab_result.patterns
    q_active = frozenset(range(len(slab_spans))) if automatic else design_patterns[-1].active_live_spans
    q_pattern = LoadPattern("Q", q_active, "所选跨活载单独作用（不含恒载），用于传力追踪")
    patterns = [design_patterns[0], q_pattern, *design_patterns[1:]]
    slab_cases = dict(slab_result.cases)
    slab_cases["Q"] = analyze_member(slab_model, set(q_active), include_dead=False)
    slab_result = build_member_envelope_from_cases(slab_model, patterns, slab_cases)
    secondary_patterns = patterns
    main_patterns = patterns
    if not automatic:
        secondary_active = frozenset(parse_span_selection(params.get("secondary_live_spans_text", ""), len(secondary_spans), "次梁活载跨"))
        main_active = frozenset(parse_span_selection(params.get("main_live_spans_text", ""), len(main_spans), "主梁活载跨"))
        secondary_patterns = [
            patterns[0], LoadPattern("Q", secondary_active, "同一全局工况下的次梁活载单独作用"),
            LoadPattern(patterns[-1].name, secondary_active, "同一全局工况下的次梁活载跨"),
        ]
        main_patterns = [
            patterns[0], LoadPattern("Q", main_active, "同一全局工况下的主梁活载单独作用"),
            LoadPattern(patterns[-1].name, main_active, "同一全局工况下的主梁活载跨"),
        ]

    rib_height = (params["secondary_h_mm"] - params["slab_h_mm"]) / 1000
    if rib_height <= 0:
        raise ValueError("次梁高度必须大于板厚")
    secondary_self_dead = params["gamma_g"] * params["importance_factor"] * (
        params["concrete_unit_weight"] * params["secondary_b_mm"] / 1000 * rib_height
        + params["plaster_unit_weight"] * params["plaster_thickness_mm"] / 1000 * rib_height * 2
    )
    secondary_ei = elastic_flexural_rigidity_kN_m2(e, params["secondary_b_mm"], params["secondary_h_mm"], params.get("secondary_stiffness_factor", 1.0))
    secondary_supports = parse_supports(params.get("secondary_supports_text", ""), len(secondary_spans), "次梁支承条件")
    secondary_widths = _support_widths(params, "secondary", len(secondary_spans))

    line_models: dict[int, ContinuousMemberModel] = {}
    line_cases: dict[int, dict[str, object]] = {i: {} for i in range(len(slab_spans) + 1)}
    line_loads_by_case: dict[str, tuple[float, ...]] = {}
    secondary_pattern_by_name = {pattern.name: pattern for pattern in secondary_patterns}
    for pattern in patterns:
        slab_case = slab_result.cases[pattern.name]
        line_loads = slab_support_line_reactions(slab_model, slab_case, strip_width)
        line_loads_by_case[pattern.name] = line_loads
        for line_index, transferred_udl in enumerate(line_loads):
            if pattern.name == "G":
                udls = tuple(transferred_udl + secondary_self_dead for _ in secondary_spans)
            else:
                active_secondary = secondary_pattern_by_name[pattern.name].active_live_spans
                dead_line = line_loads_by_case["G"][line_index]
                live_line = transferred_udl if pattern.name == "Q" else transferred_udl - dead_line
                udls = tuple(
                    (0.0 if pattern.name == "Q" else dead_line + secondary_self_dead)
                    + (live_line if span_index in active_secondary else 0.0)
                    for span_index in range(len(secondary_spans))
                )
            case_model = ContinuousMemberModel(
                "次梁", secondary_spans, secondary_ei,
                udls,
                tuple(0.0 for _ in secondary_spans), secondary_widths, secondary_supports,
                direction_name="30m方向",
            )
            line_models.setdefault(line_index, case_model)
            line_cases[line_index][pattern.name] = analyze_member(case_model, set(), include_dead=True)

    secondary_lines = {
        index: build_member_envelope_from_cases(line_models[index], secondary_patterns, cases)
        for index, cases in line_cases.items()
    }
    display_line = 1 if len(slab_spans) > 1 else 0
    secondary_result = secondary_lines[display_line]

    manual_positions = str(params.get("main_point_positions_text", "")).strip()
    if manual_positions:
        try:
            positions = tuple(sorted(float(item.strip()) for item in manual_positions.replace("，", ",").split(",") if item.strip()))
        except ValueError as exc:
            raise ValueError("主梁集中力位置应使用逗号分隔的数字") from exc
        if not positions or any(position <= 0 or position >= sum(main_spans) for position in positions):
            raise ValueError(f"主梁集中力位置必须大于 0 且小于总长度 {sum(main_spans):g} m")
        if len(set(positions)) != len(positions):
            raise ValueError("主梁集中力位置不能重复")
        point_map = [(x, 1 + i % max(len(slab_spans) - 1, 1)) for i, x in enumerate(positions)]
    else:
        point_map = []
        offset = 0.0
        interior_lines = list(enumerate(slab_model.boundaries_m[1:-1], start=1))
        for length in main_spans:
            point_map.extend((offset + x, line_index) for line_index, x in interior_lines)
            offset += length

    selected_secondary_support = int(params.get("secondary_to_main_support_number", len(secondary_spans) // 2 + 1)) - 1
    if not 0 <= selected_secondary_support <= len(secondary_spans):
        raise ValueError(f"次梁传主梁的交点支座编号应在 1～{len(secondary_spans) + 1} 之间")
    main_rib_height = (params["main_h_mm"] - params["slab_h_mm"]) / 1000
    if main_rib_height <= 0:
        raise ValueError("主梁高度必须大于板厚")
    main_self_dead = params["gamma_g"] * params["importance_factor"] * (
        params["concrete_unit_weight"] * params["main_b_mm"] / 1000 * main_rib_height
        + params["plaster_unit_weight"] * params["plaster_thickness_mm"] / 1000 * main_rib_height * 2
    )
    main_ei = elastic_flexural_rigidity_kN_m2(e, params["main_b_mm"], params["main_h_mm"], params.get("main_stiffness_factor", 1.0))
    main_supports = parse_supports(params.get("main_supports_text", ""), len(main_spans), "主梁支承条件")
    main_widths = _support_widths(params, "main", len(main_spans))
    main_cases: dict[str, object] = {}
    transfer_rows: list[dict] = []
    base_points: list[MemberPointLoad] = []
    for pattern in patterns:
        points: list[MemberPointLoad] = []
        for point_number, (position, line_index) in enumerate(point_map, start=1):
            secondary_case = line_cases[line_index][pattern.name]
            reactions = _all_support_line_reactions(line_models[line_index], secondary_case)
            point_value = reactions[selected_secondary_support]
            source = f"板支承线{line_index + 1}→次梁支座{selected_secondary_support + 1}交点P{point_number}"
            points.append(MemberPointLoad(position, point_value, 0.0, source))
            transfer_rows.append({
                "全局工况": pattern.name, "传递阶段": "板→次梁→主梁", "板支承线": line_index + 1,
                "主梁交点 x (m)": position, "板传次梁线荷载 (kN/m)": line_loads_by_case[pattern.name][line_index],
                "次梁传主梁反力 (kN)": point_value, "荷载来源": source,
                "来源": f"{source}矩阵反力",
            })
        case_model = ContinuousMemberModel(
            "主梁", main_spans, main_ei, tuple(0.0 if pattern.name == "Q" else main_self_dead for _ in main_spans), tuple(0.0 for _ in main_spans),
            main_widths, main_supports, tuple(points), direction_name="18m方向",
        )
        if pattern.name == "G":
            base_points = points
            main_model = case_model
        main_cases[pattern.name] = analyze_member(case_model, set(), include_dead=True)
    main_result = build_member_envelope_from_cases(main_model, main_patterns, main_cases)
    transfer_df = pd.DataFrame(transfer_rows)
    global_case_df = pd.DataFrame([
        {"全局工况": pattern.name, "活载跨": ",".join(str(i + 1) for i in sorted(pattern.active_live_spans)) or "无",
         "板结果工况": pattern.name, "次梁结果工况": pattern.name, "主梁结果工况": pattern.name,
         "说明": "同一工况依次完成板求解、逐支承线传次梁、逐交点传主梁"}
        for pattern in patterns
    ])
    return ProjectMatrixResult(
        slab=slab_result,
        secondary=secondary_result,
        main=main_result,
        slab_design_df=design_control_sections(slab_result, "slab", params["strip_width_m"] * 1000, params["slab_h_mm"], params["slab_h0_mm"], params["fc"], params["fy_slab"]),
        secondary_design_df=design_control_sections(secondary_result, "beam", params["secondary_b_mm"], params["secondary_h_mm"], params["secondary_h0_mm"], params["fc"], params["fy_beam"], params["fyv"], flange_width_mm=params.get("secondary_flange_width_mm"), flange_thickness_mm=params["slab_h_mm"]),
        main_design_df=design_control_sections(main_result, "beam", params["main_b_mm"], params["main_h_mm"], params["main_h0_mm"], params["fc"], params["fy_beam"], params["fyv"], flange_width_mm=params.get("main_flange_width_mm"), flange_thickness_mm=params["slab_h_mm"]),
        transfer_df=transfer_df,
        global_case_df=global_case_df,
        secondary_lines=secondary_lines,
    )


def member_tables(result: MemberEnvelopeResult, design_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    prefix = result.model.member
    load_rows = [
        {"荷载类型": "跨内均布荷载", "跨号": index + 1, "位置 x (m)": "全跨", "恒载设计分量": result.model.dead_udl_kN_m[index], "活载设计分量": result.model.live_udl_kN_m[index], "单位": "kN/m", "来源": "构件自重及上一级矩阵反力"}
        for index in range(len(result.model.spans_m))
    ]
    load_rows.extend(
        {"荷载类型": "节点集中荷载", "跨号": result.model.span_at(point.x_m) + 1, "位置 x (m)": point.x_m, "恒载设计分量": point.dead_down_kN, "活载设计分量": point.live_down_kN, "单位": "kN", "来源": point.source}
        for point in result.model.point_loads
    )
    return {
        f"{prefix}矩阵荷载表": pd.DataFrame(load_rows),
        f"{prefix}节点表": result.node_df,
        f"{prefix}单元表": result.element_df,
        f"{prefix}支承条件表": result.node_df[["节点", "x (m)", "竖向约束", "转角约束", "说明"]],
        f"{prefix}荷载工况表": result.load_case_df,
        f"{prefix}总刚度矩阵摘要": result.stiffness_summary_df,
        f"{prefix}节点位移表": result.displacement_df,
        f"{prefix}支座反力表": result.reaction_df,
        f"{prefix}单元杆端内力表": result.end_force_df,
        f"{prefix}控制截面内力包络表": result.control_df,
        f"{prefix}逐控制截面配筋表": design_df,
        f"{prefix}连续内力包络数据": result.envelope_df,
    }
