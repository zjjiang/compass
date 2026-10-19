# compass · 个人 OKR 存储系统

> 方向盘（compass）—— deputy（事业）/ steward（生活）之后的第三个同构后端，
> 管**方向**：个人 OKR 的存储、快照版本与回顾。核心：**分身提议 → 你批准 → 快照定格**。
> 「人类做门禁」是不可动摇的设计：MCP 层只有读 + propose，没有任何直写工具。

## 与 deputy / steward 的关系（同构约定）

- 技术栈：Python 3.12+ / SQLite（`data/compass.db`，.gitignore，`COMPASS_DB` 可覆盖）
  + FastMCP + FastAPI。包管理用 `uv`。
- 版本语义是 compass 的立身之本：**版本 = 完整 OKR 快照，至多一个 active**；
  归档只读；打快照自动激活新版本；回滚 = 切活跃指针。动版本逻辑先读
  `app/store/versions.py` 的模块 docstring。
- 领域规则集中在 `app/domain.py`（白名单、progress 边界、DomainError），
  store 层与 MCP/API 层都认它，不散落。
- doc 编辑走**纯函数变换**（`app/store/okr.py` 上半部分：doc 进 doc 出，直接单测），
  落库包装只是薄薄一层事务。

## 开发流程（强制，三条铁律）

与 deputy / steward 一致，任何非平凡改动必须：

1. **OpenSpec 先行** — `/opsx:propose` 立提案（proposal → specs → design → tasks），
   用户审阅通过前**不动手写代码**。零风险改动（错字/格式）除外。
2. **TDD** — Red → Green → Refactor，先写失败测试再实现。测试跑 `uv run pytest -q`。
3. **PR 合入，push 先问** — **任何 git push 之前必须先找用户确认**（docs 改动也不例外），
   不直推 main。流程：`git switch -c feat/<简述>` → 提交 → **用户确认** → push →
   `gh pr create` → 测试绿 + 用户审阅后合并。一个 OpenSpec change 对应一个分支/PR。

## 命令

```bash
uv sync                                  # 装依赖
uv run pytest -q                         # 测试（41 个，改完必须全绿）
uv run ruff check .                      # lint
uv run python scripts/smoke_stdio.py     # stdio 全链路冒烟（动 MCP/门禁后必跑）
uv run uvicorn app.api:app --port 8902   # 看板（注意 8901 是 steward，8899 是 deputy）
```

## 契约红线（改坏了会静默腐蚀信任的地方）

- **门禁不泄漏**：MCP 工具名 ∩ 写操作 = 只有 `propose`。
  `tests/test_mcp_contract.py` 有契约测试，新增工具先想清楚该不该让分身直写。
- **至多一个 active**：任何版本状态变更必须在 `db.transaction()` 内完成
  （先归档旧的，再激活新的），事务外改状态是 bug。
- **归档只读**：任何编辑路径只准碰活跃版本；历史快照永不改写。
- **数据不出墙**：`data/`、`*.db` 永远 gitignore；不要把 OKR 内容发给任何外部服务。

## 范围纪律（第一阶段）

只做：OKR 存储（O + KR + progress）+ 快照版本 + 门禁 + 轻量回顾。
不做：KR 权重、自动进度算法、周期（季度/年度）模型、版本 diff、Web 编辑、
多用户/鉴权（localhost only）。想扩展先走 OpenSpec 提案。
