# add-gate-approve-reject-mcp · 设计

## 决策 1：与 deputy 完全同名同义（approve_proposal / reject_proposal）

同构是这个项目群的立身约定：同名工具降低分身与用户的双方心智成本。参数面也照抄：
`approve_proposal(proposal_id: int)`、`reject_proposal(proposal_id: int, note: str = "")`。

## 决策 2：门禁语义从"物理隔离"改为"角色隔离"

现状（严格版）：写工具面 = {propose}，approve 只在 HTTP 层 → 人类必须换 App。
目标（deputy 版）：写工具面 = {propose, approve_proposal, reject_proposal}，但后两者的
**角色是"用户专属动作"**，纪律写进 docstring + INSTRUCTIONS，与 deputy avatar-guide
铁律 2 一字不差地同构：

> 绝不自批——approve/reject 是用户的专属动作。仅当用户明确说"批准/驳回第 N 条"时
> 才代为调用；没有明确指令，一律不碰。

这是约定层面的软门禁，与 deputy 一致。Web 看板保留为硬通道（分身够不着 HTTP 层的
按钮，那仍是纯人类直写）。两层叠加：想绕过人，分身得先违反章程；看板那条路则根本
绕不过。

## 决策 3：store 层零改动

`app/store/proposals.py` 的 `approve(id)` / `reject(id, note=)` 已存在且被 API 层使用，
事务边界（批准 = 派发 + 落库，单事务）已在原实现里验证过。MCP 工具只是薄包装，
doc 进 doc 出的纯函数变换不需要动。RISK：无已知风险；唯一注意点是错误映射要复用
`_tool_error`，让"提议不存在"等 DomainError 以 ToolError 形态冒出。

## 决策 4：契约测试守新门

`tests/test_mcp_contract.py` 的 `test_tool_inventory` 是"门禁不泄漏"的守门测试，
本次把它从 5 工具改成 7 工具，同时保留 write-prefix 断言（`approve_` / `reject_`
不在 `add_/update_/remove_/create_/switch_` 前缀内，天然通过）。新增三条链路测试：
对话内批准生效、驳回作废、批准未知提议报 ToolError。

## 影响面

- `app/mcp_server.py`：+2 工具（约 +30 行）、INSTRUCTIONS 章程扩"绝不自批"铁律。
- `tests/test_mcp_contract.py`：清单断言扩面 + 3 条新测试。
- 文档口径：`CLAUDE.md`（红线表述）、`README.md`（工具全集、门禁流程）、
  `docs/lobster-setup.md`（§5 人设、验收链路 2 的批准方式）。
- 不动：store 层、API 层、`app/domain.py`、版本逻辑、数据库 schema。

## 非目标

- 不做"批准需二次确认"之类的复杂双人规则（第一阶段范围纪律）。
- 不改看板 UI。
- 不引入 openclaw 侧的配置改动（工具面变了，`openclaw mcp reload` 即可）。
