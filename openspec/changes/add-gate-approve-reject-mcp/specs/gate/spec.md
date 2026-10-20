# gate 变更（delta）

## ADDED Requirements

### Requirement: 分身写真源仅经 propose 门禁

分身（MCP 层）SHALL 只能通过 `propose(action, args, reason)` 向真源提交写操作；提议进入队列时 SHALL 保持 `pending` 且不改变真源。`reason` 为空或纯空白时系统 SHALL 拒绝。

#### Scenario: 提议不直接生效

- **WHEN** 分身调用 `propose(update_key_result, {kr_id, progress: 60}, reason)`
- **THEN** 队列中出现一条 `pending` 提议
- **THEN** 真源中该 KR 的 progress 仍为旧值

### Requirement: 批准/驳回是用户专属动作，双通道放行

系统 SHALL 提供两个用户专属的门禁放行动作，且仅限两条通道：

1. **Web 看板**（人类直写端点）：`POST /api/proposals/{id}/approve`、`POST /api/proposals/{id}/reject`；
2. **对话内代为调用**（MCP 工具 `approve_proposal(proposal_id)` / `reject_proposal(proposal_id, note)`）：分身仅当用户在对话中明确说出"批准/驳回某条提议"时才 SHALL 代为调用。

分身 SHALL NOT 在用户未明确拍板的情况下自行调用批准/驳回（**绝不自批**）。批准成功后系统 SHALL 立即派发该提议到真源并落库；驳回 SHALL 将提议作废且真源不变。

#### Scenario: 对话内批准后生效

- **WHEN** 用户在对话里说"批准第 N 条"，分身调用 `approve_proposal(N)`
- **THEN** 提议状态变为 `approved`，其写操作被派发执行
- **THEN** 分身随后读取 `get_active_okr` 能看到改动已生效

#### Scenario: 对话内驳回后作废

- **WHEN** 用户说"驳回第 N 条"，分身调用 `reject_proposal(N, note)`
- **THEN** 提议状态变为 `rejected`，真源不变

#### Scenario: 批准不存在的提议

- **WHEN** 对任一通道调用批准，`proposal_id` 不存在
- **THEN** 返回明确错误（"提议不存在"），队列与真源均不变

#### Scenario: 提议规则不过则批准失败且保持 pending

- **WHEN** 批准一条其写操作无法通过领域规则校验的提议（如 progress 越界）
- **THEN** 系统 SHALL 拒绝执行并给出原因
- **THEN** 该提议保持 `pending`，可修正后重新处理

### Requirement: MCP 工具面契约

MCP 工具全集 SHALL 为只读四件套（`get_active_okr` / `list_versions` / `get_version` / `review`）加 `propose` / `approve_proposal` / `reject_proposal`，不多不少。分身对真源的**自主**写入口 SHALL 有且仅有 `propose`；`approve_proposal` / `reject_proposal` 的工具描述 SHALL 明示"用户专属、绝不自批"的纪律。

#### Scenario: 工具清单契约

- **WHEN** 与 compass MCP server 握手并列出工具
- **THEN** 工具集合恰好等于上述 7 个

#### Scenario: 章程随握手下发

- **WHEN** 构造 MCP server
- **THEN** `instructions` 非空且包含 `propose`、"批准"与"绝不自批"纪律
