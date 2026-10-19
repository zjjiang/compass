"""stdio 全链路冒烟：部署后跑一遍，验证 MCP 链路 + 门禁 + 版本回滚。

用法：uv run python scripts/smoke_stdio.py
（临时库，不碰真实 data/compass.db）
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 仓库根，供 import app.*

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError

from app.store import proposals  # 门禁审批是"人类侧"动作，直接走 store


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # 父进程（人类侧审批）与子进程（MCP server）必须指向同一个临时库
        smoke_db = str(Path(tmp) / "smoke.db")
        os.environ["COMPASS_DB"] = smoke_db
        env = {**os.environ, "COMPASS_DB": smoke_db}
        transport = StdioTransport(
            "uv", ["run", "python", "-m", "app.mcp_server"], env=env, cwd=str(Path(__file__).resolve().parents[1])
        )
        async with Client(transport) as client:
            tools = {t.name for t in await client.list_tools()}
            assert tools == {"get_active_okr", "list_versions", "get_version", "review", "propose"}, tools
            print(f"1. 工具清单 OK：{sorted(tools)}")

            state = (await client.call_tool("get_active_okr")).data
            assert state["status"] == "active" and state["summary"]["objective_count"] == 0
            print("2. 空库自举 OK：初始活跃版本就绪")

            # 提议：加目标 + 加 KR（扣队列，不生效）
            p1 = (
                await client.call_tool(
                    "propose",
                    {"action": "add_objective", "args": {"title": "冒烟目标"}, "reason": "冒烟测试"},
                )
            ).data
            assert p1["status"] == "pending"
            state = (await client.call_tool("get_active_okr")).data
            assert state["summary"]["objective_count"] == 0, "门禁泄漏：提议未批准就生效了"
            print("3. 门禁隔离 OK：提议 pending，真源未动")

            proposals.approve(p1["id"])
            p2 = (
                await client.call_tool(
                    "propose",
                    {
                        "action": "add_key_result",
                        "args": {"objective_id": "o-1", "title": "冒烟 KR"},
                        "reason": "冒烟测试",
                    },
                )
            ).data
            proposals.approve(p2["id"])
            state = (await client.call_tool("get_active_okr")).data
            assert state["summary"]["objective_count"] == 1 and state["summary"]["kr_count"] == 1
            print("4. 批准派发 OK：目标与 KR 已落活跃版本")

            p3 = (
                await client.call_tool(
                    "propose",
                    {"action": "update_key_result", "args": {"kr_id": "kr-1", "progress": 40}, "reason": "进展"},
                )
            ).data
            proposals.approve(p3["id"])
            review = (await client.call_tool("review")).data
            assert review["overall_progress"] == 40
            print("5. 进度更新 OK：review 40%")

            # 版本：打快照 → 提议非法动作报错 → 回滚
            p4 = (
                await client.call_tool(
                    "propose",
                    {"action": "create_version", "args": {"label": "冒烟快照"}, "reason": "定格"},
                )
            ).data
            proposals.approve(p4["id"])
            rows = (await client.call_tool("list_versions")).data
            assert len(rows) == 2 and rows[0]["status"] == "active"
            old_id = rows[1]["id"]

            try:
                await client.call_tool(
                    "propose", {"action": "nuke", "args": {}, "reason": "非法动作"}
                )
                raise AssertionError("非法动作竟然被收下了")
            except ToolError as e:
                assert "未知提议动作" in str(e)
            print("6. 白名单 OK：非法动作被拒")

            p5 = (
                await client.call_tool(
                    "propose",
                    {"action": "switch_active", "args": {"version_id": old_id}, "reason": "回滚"},
                )
            ).data
            proposals.approve(p5["id"])
            state = (await client.call_tool("get_active_okr")).data
            # 初始版本就是此前被编辑的活跃版本：回滚后应看到 1 目标 1 KR、进度 40
            assert state["id"] == old_id
            assert state["summary"]["objective_count"] == 1
            assert state["summary"]["overall_progress"] == 40
            print("7. 回滚 OK：切回快照前的版本（数据分毫不差）")

    print("\n全部通过 ✅  stdio 链路 + 门禁 + 版本管理就绪。")


if __name__ == "__main__":
    asyncio.run(main())
