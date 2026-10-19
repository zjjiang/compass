"""compass MCP server —— 分身（OpenClaw/龙虾）的唯一入口。

铁律：这里只有"读"和"提议"。任何写操作必须走 propose(...) 扣进门禁队列，
用户批准（Web 看板）后才落地。本文件里不存在直接改真源的工具。
"""
from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from . import domain
from .store import ensure_ready, okr, proposals, versions

INSTRUCTIONS = """\
compass · 个人 OKR 存储系统 —— 你（分身）是它的唯一操作入口，用户是门禁。

【你能做什么】
- 随时读：get_active_okr（当前活跃版本全文 + 进度汇总）、list_versions /
  get_version（历史快照）、review（轻量回顾）。
- 想写只能提：propose(action, args, reason) 把写操作扣进门禁队列，
  用户在 Web 看板批准后才生效。你没有其他任何写工具。

【门禁动作（action 白名单）】
- create_version   {label, note?, copy_active?}   打快照并自动激活（copy_active 默认 true）
- switch_active    {version_id}                    回滚/切换活跃版本
- add_objective    {title, note?}
- update_objective {objective_id, title?, note?}
- remove_objective {objective_id}
- add_key_result   {objective_id, title, note?}
- update_key_result {kr_id, title?, progress?, note?}   progress 为 0-100 整数
- remove_key_result {kr_id}

【纪律】
1. reason 必填且要具体：一句话说清"为什么提这个、依据是什么"，供用户快速拍板。
2. 版本语义：活跃版本可编辑；打快照会归档当前版本并激活新版本；回滚 = switch_active。
3. progress 必须是 0-100 的整数；用户没说清就不猜，先问。
4. 数据不出墙：所有数据只在本地 SQLite，不要把 OKR 内容外发到别处。
"""

mcp = FastMCP("compass", instructions=INSTRUCTIONS)


def _tool_error(exc: Exception) -> ToolError:
    return ToolError(str(exc))


@mcp.tool
def get_active_okr() -> dict:
    """读当前活跃版本：全部 Objectives / Key Results + 进度汇总。"""
    try:
        ensure_ready()
        return okr.get_active_okr()
    except (domain.DomainError, KeyError) as e:
        raise _tool_error(e) from e


@mcp.tool
def list_versions() -> list[dict]:
    """列全部版本快照（最新在前），含 status（active/archived）与 parent_id。"""
    try:
        ensure_ready()
        return versions.list_versions()
    except (domain.DomainError, KeyError) as e:
        raise _tool_error(e) from e


@mcp.tool
def get_version(version_id: int) -> dict:
    """看任意历史版本快照（只读，不会切换活跃版本）。"""
    try:
        ensure_ready()
        return versions.get_version(version_id)
    except (domain.DomainError, KeyError) as e:
        raise _tool_error(e) from e


@mcp.tool
def review() -> dict:
    """轻量回顾：各 Objective 的 KR 均分进度、整体进度、完成/未启动计数。"""
    try:
        ensure_ready()
        return okr.review_active()
    except (domain.DomainError, KeyError) as e:
        raise _tool_error(e) from e


@mcp.tool
def propose(action: str, args: dict, reason: str) -> dict:
    """【门禁】提交一条写操作提议，扣进队列等用户批准，绝不直接生效。

    action 取值（及 args 必填键）：
      - create_version    {label, note?, copy_active?}   打快照并自动激活
      - switch_active     {version_id}                   回滚/切换活跃版本
      - add_objective     {title, note?}
      - update_objective  {objective_id, title?, note?}
      - remove_objective  {objective_id}
      - add_key_result    {objective_id, title, note?}
      - update_key_result {kr_id, title?, progress?, note?}
      - remove_key_result {kr_id}

    reason 必填：一句话说清"为什么提这个、依据是什么"，供用户在门禁处快速拍板。
    提议不会立即生效；用户在 Web 看板批准后才落库，驳回则作废。
    """
    try:
        ensure_ready()
        return proposals.propose(action, args, reason)
    except (domain.DomainError, KeyError) as e:
        raise _tool_error(e) from e


if __name__ == "__main__":
    mcp.run()
