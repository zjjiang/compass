# add-gate-approve-reject-mcp

## Why

compass 的门禁比 deputy 更严：MCP 层只有 `propose`，批准/驳回只留在 Web 看板（8902）。结果是用户在龙虾对话里听到"已扣进门禁"后，必须切到浏览器才能拍板——而 deputy 的同款门禁早已把 `approve_proposal` / `reject_proposal` 做成 MCP 工具，用户在对话里说"批准第 N 条"、分身代为调用即生效。两个同构后端的门禁语义应当一致：**门禁的本质是"人在对话里明确拍板"，而不是"人必须换一个 App"**。现在的严格反而破坏了同构、切断了方向盘最顺的那条链路。

## What Changes

- **`app/mcp_server.py` 新增两个 MCP 工具**（与 deputy 同名同义）：
  - `approve_proposal(proposal_id)` —— 用户批准某条提议，系统执行并落库；
  - `reject_proposal(proposal_id, note)` —— 用户驳回，附可选理由。
  - 两者 docstring 写死纪律：**这是留给用户的动作，分身仅在用户明确说"批准/驳回第 N 条"时代为调用，绝不自批**。
- **INSTRUCTIONS 章程更新**：门禁规则从"看板批准"扩为"看板或对话里你明确拍板"；新增铁律"绝不自批"（对齐 deputy avatar-guide 铁律 2）。
- **契约测试更新**：工具全集从"读四件套 + propose"扩为"+ approve_proposal / reject_proposal"；新增 MCP 全链路测试（对话内批准生效、驳回作废、未知提议报错）。
- **文档对齐**：README、CLAUDE.md 红线、docs/lobster-setup.md §5 人设同步改口径（"门禁不泄漏"改为"分身写真源仍只有 propose；approve/reject 是用户专属动作、仅代为调用"）。
- **Web 看板原样保留**：8902 仍是人类的直写端点，与对话批准双通道并存（deputy 同款）。

## Capabilities

### New Capabilities

- `gate`：提议门禁的完整契约——分身写真源仅 `propose`；批准/驳回是用户专属动作，双通道（Web 看板直调 + 对话内明确拍板后分身代调）；批准才落库、驳回即作废；绝不自批。

### Modified Capabilities

（无——这是 compass 首个 OpenSpec capability，现有版本快照能力不在本提案范围。）

## Impact

- `app/mcp_server.py`：+2 工具、INSTRUCTIONS 扩一段。
- `tests/test_mcp_contract.py`：工具清单断言扩面 + 新增 3 条批准/驳回链路测试。
- `README.md` / `CLAUDE.md` / `docs/lobster-setup.md`：口径同步。
- 不碰 store 层（`proposals.approve/reject` 已存在且被 API 层使用）、不碰版本逻辑、不碰数据库。
