"""MCP 契约测试：工具清单、门禁不泄漏、instructions 章程、全链路。"""
from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.mcp_server import mcp
from app.store import ensure_ready, okr, proposals

pytestmark = pytest.mark.anyio

READ_TOOLS = {"get_active_okr", "list_versions", "get_version", "review"}
USER_TOOLS = {"propose", "approve_proposal", "reject_proposal"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("COMPASS_DB", str(tmp_path / "mcp.db"))


async def call(client: Client, name: str, arguments: dict | None = None):
    result = await client.call_tool(name, arguments or {})
    return result.data


async def test_tool_inventory(isolated_db):
    """工具全集 = 只读四件套 + 门禁三件套，一个都不能多。"""
    async with Client(mcp) as client:
        tools = {t.name for t in await client.list_tools()}
    assert tools == READ_TOOLS | USER_TOOLS
    write_prefixes = ("add_", "update_", "remove_", "create_", "switch_")
    assert not any(t.startswith(write_prefixes) for t in tools)


async def test_user_tools_marked_exclusive(isolated_db):
    """approve/reject 是用户专属动作，工具描述必须写明"绝不自批"纪律。"""
    async with Client(mcp) as client:
        descriptions = {t.name: t.description or "" for t in await client.list_tools()}
    for name in ("approve_proposal", "reject_proposal"):
        assert "绝不自批" in descriptions[name], f"{name} 缺少专属纪律说明"


def test_instructions_charter():
    """instructions 章程必须随握手下发，且写明门禁规矩与绝不自批纪律。"""
    assert mcp.instructions
    assert "propose" in mcp.instructions
    assert "批准" in mcp.instructions
    assert "绝不自批" in mcp.instructions


async def test_read_tools_on_fresh_db(isolated_db):
    async with Client(mcp) as client:
        state = await call(client, "get_active_okr")
        assert state["status"] == "active"
        assert state["summary"]["objective_count"] == 0

        rows = await call(client, "list_versions")
        assert len(rows) == 1

        one = await call(client, "get_version", {"version_id": rows[0]["id"]})
        assert one["id"] == rows[0]["id"]

        overview = await call(client, "review")
        assert overview["overall_progress"] == 0


async def test_get_version_unknown_raises_tool_error(isolated_db):
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="版本不存在"):
            await call(client, "get_version", {"version_id": 999})


async def test_propose_invalid_action_raises_tool_error(isolated_db):
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="未知提议动作"):
            await call(client, "propose", {"action": "wipe", "args": {}, "reason": "想清库"})


async def test_propose_missing_reason_raises_tool_error(isolated_db):
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="理由"):
            await call(
                client, "propose", {"action": "add_objective", "args": {"title": "O"}, "reason": " "}
            )


async def test_full_gate_flow_through_mcp(isolated_db):
    """分身视角全链路：读 → propose（不生效）→ 人批准 → 再读生效。"""
    ensure_ready()  # store 直调前先建库（生产里由 MCP/API 入口负责）
    okr.add_objective_to_active("O1")
    okr.add_key_result_to_active("o-1", "kr1")

    async with Client(mcp) as client:
        # 提议更新进度：队列里有，真源没动
        proposal = await call(
            client,
            "propose",
            {
                "action": "update_key_result",
                "args": {"kr_id": "kr-1", "progress": 60},
                "reason": "本周完成六成",
            },
        )
        assert proposal["status"] == "pending"
        state = await call(client, "get_active_okr")
        assert state["doc"]["objectives"][0]["key_results"][0]["progress"] == 0

    # 人批准（Web/CLI 侧，不经 MCP）
    proposals.approve(proposal["id"])

    async with Client(mcp) as client:
        state = await call(client, "get_active_okr")
        assert state["doc"]["objectives"][0]["key_results"][0]["progress"] == 60
        overview = await call(client, "review")
        assert overview["overall_progress"] == 60


async def test_conversation_approve_flow(isolated_db):
    """对话内批准链路：propose → 人说"批准" → 分身代调 approve_proposal → 生效。"""
    ensure_ready()
    okr.add_objective_to_active("O1")
    okr.add_key_result_to_active("o-1", "kr1")

    async with Client(mcp) as client:
        proposal = await call(
            client,
            "propose",
            {
                "action": "update_key_result",
                "args": {"kr_id": "kr-1", "progress": 80},
                "reason": "用户口述本周完成八成",
            },
        )
        approved = await call(client, "approve_proposal", {"proposal_id": proposal["id"]})
        assert approved["proposal"]["status"] == "approved"

        state = await call(client, "get_active_okr")
        assert state["doc"]["objectives"][0]["key_results"][0]["progress"] == 80


async def test_conversation_reject_flow(isolated_db):
    """对话内驳回链路：propose → 分身代调 reject_proposal → 提议作废、真源不变。"""
    ensure_ready()
    okr.add_objective_to_active("O1")

    async with Client(mcp) as client:
        proposal = await call(
            client,
            "propose",
            {"action": "add_objective", "args": {"title": "不该加的"}, "reason": "试试驳回"},
        )
        rejected = await call(
            client,
            "reject_proposal",
            {"proposal_id": proposal["id"], "note": "先不加"},
        )
        assert rejected["status"] == "rejected"
        assert rejected["decision_note"] == "先不加"

        state = await call(client, "get_active_okr")
        assert state["summary"]["objective_count"] == 1  # "不该加的"没进来


async def test_approve_unknown_proposal_raises_tool_error(isolated_db):
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="提议不存在"):
            await call(client, "approve_proposal", {"proposal_id": 999})


async def test_double_approve_raises_tool_error(isolated_db):
    """同一提议不能批两次。"""
    ensure_ready()
    okr.add_objective_to_active("O1")

    async with Client(mcp) as client:
        proposal = await call(
            client,
            "propose",
            {"action": "add_objective", "args": {"title": "O2"}, "reason": "只批一次"},
        )
        await call(client, "approve_proposal", {"proposal_id": proposal["id"]})
        with pytest.raises(ToolError, match="不能重复批准"):
            await call(client, "approve_proposal", {"proposal_id": proposal["id"]})
