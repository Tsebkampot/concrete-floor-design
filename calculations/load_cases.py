"""连续梁活载工况生成。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class LoadPattern:
    name: str
    active_live_spans: frozenset[int]
    description: str


def enumerate_live_load_patterns(
    span_count: int,
    automatic: bool = True,
    manual_active_spans: set[int] | None = None,
) -> list[LoadPattern]:
    """枚举恒载工况及逐跨活载组合；自动枚举最多支持 8 跨。"""
    if span_count <= 0:
        raise ValueError("跨数必须大于 0")
    if span_count > 8 and automatic:
        raise ValueError("自动枚举最多支持 8 跨，请减少跨数或关闭自动最不利布置")
    patterns = [LoadPattern("G", frozenset(), "全部跨恒载")]
    if not automatic:
        active = frozenset(range(span_count) if manual_active_spans is None else manual_active_spans)
        if any(index < 0 or index >= span_count for index in active):
            raise ValueError("手动活载跨号超出构件跨数")
        label = ",".join(str(i + 1) for i in sorted(active)) or "无"
        return patterns + [LoadPattern(f"G+Q[{label}]", active, f"手动在第 {label} 跨布置活载")]
    indices = range(span_count)
    for count in range(1, span_count + 1):
        for subset in combinations(indices, count):
            label = ",".join(str(i + 1) for i in subset)
            patterns.append(LoadPattern(f"G+Q[{label}]", frozenset(subset), f"第 {label} 跨布置活载"))
    return patterns
