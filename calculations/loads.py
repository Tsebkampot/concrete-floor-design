"""板、次梁、主梁之间的荷载自动传递。

课程设计中常按如下路径传递荷载：

1. 板面荷载 ``kN/m2`` 乘以次梁间距 ``m``，得到次梁线荷载 ``kN/m``。
2. 次梁线荷载 ``kN/m`` 乘以次梁跨度或影响长度 ``m``，得到主梁集中力 ``kN``。

这些公式只处理单位转换和传递关系，构件自重与粉刷荷载仍在对应构件
计算模块中计算。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class LoadTransferResult:
    """荷载传递计算结果。"""

    slab_dead_kN_m2: float
    slab_live_kN_m2: float
    secondary_spacing_m: float
    secondary_span_m: float
    secondary_dead_from_slab_kN_m: float
    secondary_live_from_slab_kN_m: float
    main_dead_from_secondary_kN: float
    main_live_from_secondary_kN: float


def slab_to_secondary(area_load_kN_m2: float, spacing_m: float) -> float:
    """板面荷载转为次梁线荷载：``q_line = q_area * spacing``。"""
    if area_load_kN_m2 < 0:
        raise ValueError("板面荷载不能为负数")
    if spacing_m <= 0:
        raise ValueError("次梁间距必须大于 0")
    return area_load_kN_m2 * spacing_m


def secondary_to_main(line_load_kN_m: float, influence_length_m: float) -> float:
    """次梁线荷载转为主梁集中力：``P = q_line * influence_length``。"""
    if line_load_kN_m < 0:
        raise ValueError("次梁线荷载不能为负数")
    if influence_length_m <= 0:
        raise ValueError("影响长度必须大于 0")
    return line_load_kN_m * influence_length_m


def calculate_load_transfer(
    slab_dead_kN_m2: float,
    slab_live_kN_m2: float,
    secondary_spacing_m: float,
    secondary_span_m: float,
) -> LoadTransferResult:
    """计算板到次梁、次梁到主梁的标准值传递。"""
    secondary_dead = slab_to_secondary(slab_dead_kN_m2, secondary_spacing_m)
    secondary_live = slab_to_secondary(slab_live_kN_m2, secondary_spacing_m)
    main_dead = secondary_to_main(secondary_dead, secondary_span_m)
    main_live = secondary_to_main(secondary_live, secondary_span_m)
    return LoadTransferResult(
        slab_dead_kN_m2=slab_dead_kN_m2,
        slab_live_kN_m2=slab_live_kN_m2,
        secondary_spacing_m=secondary_spacing_m,
        secondary_span_m=secondary_span_m,
        secondary_dead_from_slab_kN_m=secondary_dead,
        secondary_live_from_slab_kN_m=secondary_live,
        main_dead_from_secondary_kN=main_dead,
        main_live_from_secondary_kN=main_live,
    )


def transfer_to_dataframe(result: LoadTransferResult) -> pd.DataFrame:
    """输出荷载传递总览表。"""
    rows = [
        [
            "板面恒载标准值",
            "输入或板计算结果",
            result.slab_dead_kN_m2,
            "kN/m2",
            "作为板到次梁的起点",
        ],
        [
            "板面活载标准值",
            "输入值",
            result.slab_live_kN_m2,
            "kN/m2",
            "作为板到次梁的起点",
        ],
        [
            "板传次梁恒载",
            "板面恒载标准值 × 次梁间距",
            result.secondary_dead_from_slab_kN_m,
            "kN/m",
            "kN/m2 × m = kN/m",
        ],
        [
            "板传次梁活载",
            "板面活载标准值 × 次梁间距",
            result.secondary_live_from_slab_kN_m,
            "kN/m",
            "kN/m2 × m = kN/m",
        ],
        [
            "次梁传主梁恒载集中力",
            "次梁恒载线荷载 × 次梁跨度或影响长度",
            result.main_dead_from_secondary_kN,
            "kN",
            "kN/m × m = kN",
        ],
        [
            "次梁传主梁活载集中力",
            "次梁活载线荷载 × 次梁跨度或影响长度",
            result.main_live_from_secondary_kN,
            "kN",
            "kN/m × m = kN",
        ],
    ]
    return pd.DataFrame(rows, columns=["项目", "公式", "数值", "单位", "单位说明"])
