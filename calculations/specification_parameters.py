"""课程设计采用的集中规范/构造参数。

这些数值用于候选方案筛选，不替代对具体规范版本、环境类别和抗震等级的
逐条核对。程序输出会统一标注“按课程近似公式估算，需人工复核”。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CourseSpecificationParameters:
    min_longitudinal_ratio: float = 0.002
    max_longitudinal_ratio: float = 0.025
    compression_limit_ratio: float = 0.518
    beam_cover_mm: float = 25.0
    stirrup_diameter_mm: float = 8.0
    min_clear_bar_spacing_mm: float = 25.0
    max_stirrup_spacing_mm: float = 200.0
    min_stirrup_ratio: float = 0.0
    source_note: str = "按课程近似公式估算，需人工复核具体规范条文、环境类别和抗震等级"


COURSE_SPEC = CourseSpecificationParameters()


def parameters_table_rows() -> list[dict[str, object]]:
    return [
        {"参数": "纵筋最小配筋率", "采用值": COURSE_SPEC.min_longitudinal_ratio, "说明": COURSE_SPEC.source_note},
        {"参数": "纵筋最大配筋率", "采用值": COURSE_SPEC.max_longitudinal_ratio, "说明": COURSE_SPEC.source_note},
        {"参数": "界限受压区系数 ξb", "采用值": COURSE_SPEC.compression_limit_ratio, "说明": COURSE_SPEC.source_note},
        {"参数": "梁保护层", "采用值": COURSE_SPEC.beam_cover_mm, "单位": "mm", "说明": COURSE_SPEC.source_note},
        {"参数": "候选箍筋直径", "采用值": COURSE_SPEC.stirrup_diameter_mm, "单位": "mm", "说明": COURSE_SPEC.source_note},
        {"参数": "纵筋最小净距", "采用值": COURSE_SPEC.min_clear_bar_spacing_mm, "单位": "mm", "说明": COURSE_SPEC.source_note},
        {"参数": "箍筋最大间距", "采用值": COURSE_SPEC.max_stirrup_spacing_mm, "单位": "mm", "说明": COURSE_SPEC.source_note},
    ]
