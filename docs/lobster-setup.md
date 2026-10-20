# 龙虾（OpenClaw）接入 compass 部署指南

把 compass（个人 OKR 存储系统）挂到龙虾上，让分身能读 OKR、提议改动、出回顾——
与 deputy（事业）/ steward（生活）同构的方向盘。

> 前提认知：compass **本身不烧 token、不需要配任何 AI API**。它是纯逻辑后端
> （SQLite 快照存储 + 门禁），"智能"全来自龙虾里你配的大模型。
>
> 与 steward 的区别：compass 有**硬门禁**（同 deputy）——分身没有任何直写工具，
> 一切写操作必须 `propose` 进队列，你在看板批准后才生效。

---

## 0. 适用场景

本指南针对 **龙虾与 compass 在同一台机器** 的情况，用 **stdio** 方式接入——
最简单、无网络、无鉴权烦恼。跨机部署需另议（同 deputy 红线）。

## 1. 前置

- macOS + [uv](https://docs.astral.sh/uv/)（没有就 `brew install uv`）
- 同机已部署 deputy / steward 不是必须，但端口约定要错开：
  deputy 看板 **8899**、steward 看板 **8901**、**compass 看板 8902**。

## 2. 拉代码 + 装依赖

```bash
git clone git@github.com:zjjiang/compass.git
cd compass
uv sync
```

## 3. 验证 compass 本身能跑

```bash
uv run pytest -q                                 # 应全绿（46 个）
uv run python scripts/smoke_stdio.py             # stdio 全链路冒烟，末行应"全部通过 ✅"
uv run uvicorn app.api:app --port 8902           # 看板：浏览器开 http://127.0.0.1:8902
```

看板三块：**活跃版本**（O/KR + 进度条）、**门禁 · 待批提议**（批准/驳回按钮）、
**版本快照**（点"切到此版本"即回滚）。页面每 5 秒自动刷新。

## 4. 在龙虾里配置 MCP（stdio）

在龙虾的 MCP 配置中加一个 server（`cwd` 必须是 compass 目录的**绝对路径**）：

```json
{
  "mcpServers": {
    "compass": {
      "command": "uv",
      "args": ["run", "python", "-m", "app.mcp_server"],
      "cwd": "/绝对路径/到/compass"
    }
  }
}
```

- `uv` 不在 PATH 就换成绝对路径（`which uv` 查）。
- 可选 `env`：`{"COMPASS_DB": "/其他路径/compass.db"}`——不配就是默认
  `compass/data/compass.db`。
- 配好重启龙虾，能列出 compass 的 7 个工具（`get_active_okr` / `list_versions` /
  `get_version` / `review` / `propose` / `approve_proposal` / `reject_proposal`）
  即接入成功。工具细则以 MCP 握手 instructions 为准——那份章程随代码更新，永远最新。

## 5. 给龙虾装"方向盘"人设（关键）

把下面这段写进龙虾的角色/系统提示（或直接引用 MCP instructions）：

```
你是用户的"方向盘助手"——经 MCP 接入 compass（个人 OKR 存储）。

铁律：
1. 自主写只有提议：get_active_okr / list_versions / get_version / review 随便读；
   一切写操作（改目标、改 KR、打快照、切版本）必须 propose(action, args, reason)，
   提议不生效，等用户拍板。
2. 绝不自批：approve_proposal / reject_proposal 是用户的专属动作。仅当用户明确说
   "批准/驳回第 N 条"时才代为调用；没有明确指令，一律不碰。
3. reason 必须具体：一句话说清"为什么提这个、依据是什么"，不要写"用户要求"敷衍。
4. progress 是 0-100 的整数；用户没说清就先问，不要猜。
5. 版本语义：活跃版本可编辑；打快照（create_version）会归档当前版本并激活新版本；
   回滚 = switch_active 切活跃指针，历史永不丢。动版本前先跟用户确认 label。
6. 回顾（review）只说数据里有的：没有目标就说没有，不要硬凑成果。
7. OKR 内容不外发：不把 OKR 数据发到 compass 之外的任何服务。
```

## 6. 跑通四条链路（验收）

在龙虾对话里依次：

1. **读**：你说"我现在的 OKR 是什么" → 龙虾 `get_active_okr` → 报活跃版本与进度。
2. **提议改进度**：你说"XX 这个 KR 完成了 60%" → 龙虾 `propose(update_key_result)` →
   它告诉你"已扣进门禁，等你拍板" → 你在对话里说"批准"（龙虾代调 `approve_proposal`），
   或打开 `http://127.0.0.1:8902` 点批准 → 再问一次，进度已生效。
3. **打快照**：你说"把当前 OKR 定格成 2026Q4" → 龙虾 `propose(create_version)` →
   批准后看板版本列表多一条 active 的"2026Q4"，旧的转归档。
4. **回滚**：你说"回滚到初始版本"（或直接在看板点"切到此版本"）→
   活跃指针切回，数据分毫不差。

四条都通，方向盘就转起来了。

## 7. 数据在哪 / 怎么重置

- **位置**：`compass/data/compass.db`（gitignore，永不进仓库；`COMPASS_DB` 可覆盖）。
- **重置**：停掉看板与龙虾里的 compass 连接，删掉 db 文件即可——下次运行自动
  重建空库（幂等 init，自举一个"初始版本"）。
- **备份**：拷走 `data/compass.db`（连同 `-wal`/`-shm`）就是全量备份；版本快照
  都在里面，无需额外导出。

---

## 安全红线（勿破）

- **无鉴权，仅限 localhost**（同 deputy / steward）。跨机必先加鉴权。
- **数据不出墙**：`data/`、`*.db` 永远 gitignore。
- **看板就是门禁**：8902 上的批准按钮是真人直写端点，不要把端口转发到公网。
- **绝不自批**：approve/reject 是用户专属动作，分身只在用户明确拍板时代为调用。
  不要给 compass 加任何绕过这条的"分身自主直写"工具；要改这个设计先走 OpenSpec
  提案跟用户对齐。
