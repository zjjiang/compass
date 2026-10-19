"""门禁队列 —— compass 的安全带。

规矩（"人类做门禁"）：
  - 分身只能 propose(...)：把想做的写操作扣进队列，status=pending，绝不直接改真源。
  - 用户 approve(id)：系统才把该动作派发到真源写函数，真正落地。
  - 用户 reject(id, note)：驳回，不执行。
派发只认 domain.PROPOSAL_ACTIONS 白名单，未知动作/缺参数一律拒。

注意：approve 的派发在事务外执行（真源写函数各自持有自己的事务）；
规则不过（如目标版本不存在）时异常上抛，提议保持 pending 等人重新定夺。
"""
from __future__ import annotations

import inspect
import json
from collections.abc import Callable
from typing import Any

from .. import domain
from . import okr, versions
from .db import get_conn, transaction

_DISPATCH: dict[str, Callable[..., Any]] = {
    "create_version": versions.create_version,
    "switch_active": versions.switch_active,
    "add_objective": okr.add_objective_to_active,
    "update_objective": okr.update_objective_on_active,
    "remove_objective": okr.remove_objective_on_active,
    "add_key_result": okr.add_key_result_to_active,
    "update_key_result": okr.update_key_result_on_active,
    "remove_key_result": okr.remove_key_result_on_active,
}


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "action": row["action"],
        "args": json.loads(row["args"]),
        "reason": row["reason"],
        "by": row["by"],
        "status": row["status"],
        "created_at": row["created_at"],
        "decided_at": row["decided_at"],
        "decision_note": row["decision_note"],
    }


def _require(conn: Any, proposal_id: int) -> Any:
    row = conn.execute(
        "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"提议不存在：{proposal_id}")
    return row


def propose(
    action: str,
    args: dict[str, Any],
    reason: str,
    now: str | None = None,
    by: str = "分身",
) -> dict[str, Any]:
    """分身提交一条提议。校验动作合法 + 必需参数齐全，但不执行。"""
    if action not in domain.PROPOSAL_ACTIONS:
        raise domain.DomainError(
            f"未知提议动作 {action}，应为 {sorted(domain.PROPOSAL_ACTIONS)}"
        )
    if not isinstance(args, dict):
        raise domain.DomainError("args 必须是对象（键值对）")
    missing = [k for k in domain.PROPOSAL_ACTIONS[action] if k not in args]
    if missing:
        raise domain.DomainError(f"动作 {action} 缺少参数：{missing}")
    if not isinstance(reason, str) or not reason.strip():
        raise domain.DomainError("提议必须附理由（为什么提这个）")
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO proposals (action, args, reason, by, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (action, json.dumps(args, ensure_ascii=False), reason.strip(), by, now or _now()),
        )
        pid = cur.lastrowid
        row = _require(conn, pid)
    return _row_to_dict(row)


def list_proposals(status: str | None = "pending") -> list[dict[str, Any]]:
    """列提议。默认只看 pending（待批的）；status=None 看全部。"""
    with get_conn() as conn:
        if status is None:
            rows = conn.execute("SELECT * FROM proposals ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM proposals WHERE status = ? ORDER BY id DESC", (status,)
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_proposal(proposal_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        return _row_to_dict(_require(conn, proposal_id))


def approve(proposal_id: int, now: str | None = None) -> dict[str, Any]:
    """批准并派发落地。规则不过时异常上抛，提议保持 pending。"""
    with get_conn() as conn:
        row = _require(conn, proposal_id)
    if row["status"] != "pending":
        raise domain.DomainError(f"提议 {proposal_id} 已处理（{row['status']}），不能重复批准")

    fn = _DISPATCH[row["action"]]
    # 白名单外的键一律丢弃，只按写函数签名传参
    accepted = set(inspect.signature(fn).parameters)
    kwargs = {k: v for k, v in json.loads(row["args"]).items() if k in accepted}
    result = fn(**kwargs)

    with transaction() as conn:
        conn.execute(
            "UPDATE proposals SET status = 'approved', decided_at = ? WHERE id = ?",
            (now or _now(), proposal_id),
        )
    return {"proposal": get_proposal(proposal_id), "result": result}


def reject(
    proposal_id: int, *, note: str | None = None, now: str | None = None
) -> dict[str, Any]:
    """驳回，不执行。"""
    with transaction() as conn:
        row = _require(conn, proposal_id)
        if row["status"] != "pending":
            raise domain.DomainError(
                f"提议 {proposal_id} 已处理（{row['status']}），不能重复驳回"
            )
        conn.execute(
            "UPDATE proposals SET status = 'rejected', decided_at = ?, decision_note = ? "
            "WHERE id = ?",
            (now or _now(), note, proposal_id),
        )
    return get_proposal(proposal_id)
