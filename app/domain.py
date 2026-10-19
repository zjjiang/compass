"""领域常量与校验规则 —— 规则集中在这里，store 层与 MCP/API 层都认它。"""
from __future__ import annotations

VALID_VERSION_STATUS = frozenset({"active", "archived"})

MIN_PROGRESS = 0
MAX_PROGRESS = 100

# 门禁动作白名单：action → 必填参数键。
# 只校验"必填键存在"，具体值合法性留到 approve 派发时由 store 层把关。
PROPOSAL_ACTIONS: dict[str, tuple[str, ...]] = {
    "create_version": ("label",),
    "switch_active": ("version_id",),
    "add_objective": ("title",),
    "update_objective": ("objective_id",),
    "remove_objective": ("objective_id",),
    "add_key_result": ("objective_id", "title"),
    "update_key_result": ("kr_id",),
    "remove_key_result": ("kr_id",),
}


class DomainError(ValueError):
    """业务规则不过。MCP 层转 ToolError，Web 层转 400。"""


def validate_progress(value: object) -> int:
    """进度必须落在 [0, 100] 的整数（浮点整数值也放行，如 40.0）。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainError(f"progress 必须是数字，收到 {value!r}")
    ivalue = int(value)
    if ivalue != value:
        raise DomainError(f"progress 必须是整数，收到 {value!r}")
    if not (MIN_PROGRESS <= ivalue <= MAX_PROGRESS):
        raise DomainError(f"progress 必须在 {MIN_PROGRESS}-{MAX_PROGRESS} 之间，收到 {ivalue}")
    return ivalue


def validate_title(value: object, field: str = "title") -> str:
    """标题必填且非空白。"""
    if not isinstance(value, str) or not value.strip():
        raise DomainError(f"{field} 必填且不能为空白")
    return value.strip()
