# add-gate-approve-reject-mcp · 任务

## 1. 测试先行（RED）

- [ ] 1.1 `tests/test_mcp_contract.py::test_tool_inventory` 改为断言 7 工具全集
      （读四件套 + propose + approve_proposal + reject_proposal）——先跑，确认失败。
- [ ] 1.2 新增 `test_instructions_charter` 断言：instructions 含"绝不自批"。
- [ ] 1.3 新增 `test_conversation_approve_flow`：propose → MCP `approve_proposal` →
      `get_active_okr` 见改动生效。
- [ ] 1.4 新增 `test_conversation_reject_flow`：propose → MCP `reject_proposal(note)` →
      提议 rejected、真源不变。
- [ ] 1.5 新增 `test_approve_unknown_proposal_raises_tool_error`：报"提议不存在"。
- [ ] 1.6 跑 `uv run pytest -q`，确认以上全 RED。

## 2. 实现（GREEN）

- [ ] 2.1 `app/mcp_server.py` 加 `approve_proposal` / `reject_proposal` 薄包装
      （调 `proposals.approve/reject`，错误经 `_tool_error` 映射），docstring 写死
      "用户专属、绝不自批"纪律。
- [ ] 2.2 INSTRUCTIONS 章程：门禁段改为"看板或对话里明确拍板"双通道 + 铁律"绝不自批"。
- [ ] 2.3 跑 `uv run pytest -q` 全绿（41 + 新增 ≈ 46 个）。

## 3. 文档对齐

- [ ] 3.1 `CLAUDE.md`：红线"门禁不泄漏"改为新口径（自主写真源仅 propose；
      approve/reject 用户专属、仅代为调用），工具数 41→实际值。
- [ ] 3.2 `README.md`：MCP 工具全集、门禁流程第 3 步补"对话内批准"通道。
- [ ] 3.3 `docs/lobster-setup.md`：§5 人设铁律补"绝不自批"；§6 验收链路 2 补
      "对话里说批准"路径。

## 4. 验证与收尾

- [ ] 4.1 `uv run ruff check .` 干净。
- [ ] 4.2 `uv run python scripts/smoke_stdio.py` 全链路通过。
- [ ] 4.3 `openclaw mcp reload` + `openclaw mcp probe`：compass 变 7 工具。
- [ ] 4.4 龙虾里实测：提议 → 对话说"批准" → 生效（四条链路验收）。
- [ ] 4.5 提交（feat: 门禁批准/驳回进 MCP，与 deputy 同构）→ 用户确认 → push → PR。
