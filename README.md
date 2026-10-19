# compass · 个人 OKR 存储系统

> 一人公司的第三个同构后端（[deputy](https://github.com/zjjiang/deputy) 管事业、
> [steward](https://github.com/zjjiang/steward) 管生活，compass 管**方向**）。
> 核心一句话：**分身提议 → 你批准 → 快照定格**。

架构与 deputy / steward 同构：脑子在龙虾（OpenClaw）侧，compass 是纯逻辑后端，
不配 AI、不烧 token。数据全在本地 SQLite，永不出墙。

```
龙虾（OpenClaw）                      你（人类）
   │ 只能读 + propose(...)             │ 看板审批 / 切版本
   ▼                                  ▼
FastMCP (app/mcp_server.py)      FastAPI (app/api.py, 127.0.0.1:8902)
   └──────────┬──────────────────────┘
              ▼
    store/  版本快照（versions）+ 门禁队列（proposals）
              ▼
    SQLite (data/compass.db)   ← .gitignore，永不进仓库
```

## 版本语义（与其他系统最大的不同）

- 每个版本 = 一份**完整 OKR 快照**，同一时间**只有一个活跃版本**。
- 活跃版本可编辑；**打快照** = 复制当前活跃 → 新版本自动激活，旧的归档只读。
- **回滚** = 把活跃指针切回任一历史版本，数据分毫不差，历史永不丢。

## 跑起来

```bash
uv sync                                        # 装依赖
uv run pytest -q                               # 测试
uv run python scripts/smoke_stdio.py           # stdio 全链路冒烟
uv run uvicorn app.api:app --port 8902         # 看板 + 门禁审批（localhost only）
uv run python -m app.mcp_server                # MCP server（供龙虾接入，stdio）
```

数据库默认 `data/compass.db`（首次运行自动建库），`COMPASS_DB` 环境变量可覆盖路径。

## 龙虾（OpenClaw）接入

stdio 方式接入（与 deputy / steward 同构，龙虾与 compass 同机）：

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

完整部署手册见 [docs/lobster-setup.md](docs/lobster-setup.md)。

## 门禁流程

1. 龙虾读 `get_active_okr()` / `review()` 备料，判断该改什么。
2. 龙虾 `propose(action, args, reason)` —— 扣进队列，**不生效**。
3. 你在看板（`http://127.0.0.1:8902`）点批准 / 驳回；批准后系统派发到真源，
   规则不过（progress 越界、版本不存在等）会拒，提议保持 pending。
4. 分身与人类分工：**分身走门禁，人类直写**（审批、切版本是人类的直写端点）。

MCP 工具全集：`get_active_okr` · `list_versions` · `get_version` · `review` ·
`propose`（唯一写入口，动作白名单见 `app/domain.py::PROPOSAL_ACTIONS`）。

## 数据不出墙

代码进私有 GitHub，两处 `git clone`；**数据靠 `.gitignore` 永远留本地**：

```
data/  *.db  →  已 gitignore
```
