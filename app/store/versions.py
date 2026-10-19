"""版本层 —— 快照语义的真源。

规矩：
  - 每行 = 一份完整 OKR 快照（doc JSON），归档（archived）后只读。
  - 同一时间至多一个 active，事务内强制。
  - 打快照 = 复制当前活跃 doc → 新版本 → 自动激活，旧的转 archived。
  - 回滚 = switch_active 把活跃指针切到任一历史版本，不复制、不丢数据。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from .. import domain
from . import db

EMPTY_DOC: dict[str, Any] = {"objectives": []}
_INITIAL_LABEL = "初始版本"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "status": row["status"],
        "parent_id": row["parent_id"],
        "note": row["note"],
        "doc": json.loads(row["doc"]),
        "created_at": row["created_at"],
        "activated_at": row["activated_at"],
    }


def ensure_initial_version(conn: sqlite3.Connection) -> None:
    """空库自举：保证永远有一个活跃版本（幂等）。"""
    (count,) = conn.execute(
        "SELECT COUNT(*) FROM versions WHERE status = 'active'"
    ).fetchone()
    if count == 0:
        conn.execute(
            "INSERT INTO versions (label, status, doc, created_at, activated_at) "
            "VALUES (?, 'active', ?, ?, ?)",
            (_INITIAL_LABEL, json.dumps(EMPTY_DOC, ensure_ascii=False), _now(), _now()),
        )


def get_active() -> dict[str, Any]:
    """当前活跃版本（含已解析 doc）。"""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM versions WHERE status = 'active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise domain.DomainError("没有活跃版本，库状态异常，请检查 versions 表")
    return _row_to_dict(row)


def get_version(version_id: int) -> dict[str, Any]:
    """任意历史快照（只读）。"""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM versions WHERE id = ?", (version_id,)
        ).fetchone()
    if row is None:
        raise KeyError(f"版本不存在：{version_id}")
    return _row_to_dict(row)


def list_versions() -> list[dict[str, Any]]:
    """版本列表，最新在前。"""
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM versions ORDER BY id DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def create_version(
    label: str,
    *,
    note: str | None = None,
    copy_active: bool = True,
    now: str | None = None,
) -> dict[str, Any]:
    """打快照：复制当前活跃 doc 成新版本并自动激活，旧的转 archived。

    copy_active=False 时从空白 doc 开始（不从当前活跃复制）。
    """
    label = domain.validate_title(label, "label")
    ts = now or _now()
    with db.transaction() as conn:
        active = conn.execute(
            "SELECT * FROM versions WHERE status = 'active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        doc_json = (
            active["doc"] if (copy_active and active is not None) else json.dumps(EMPTY_DOC, ensure_ascii=False)
        )
        parent_id = active["id"] if active is not None else None
        conn.execute(
            "UPDATE versions SET status = 'archived' WHERE status = 'active'"
        )
        cur = conn.execute(
            "INSERT INTO versions (label, status, parent_id, note, doc, created_at, activated_at) "
            "VALUES (?, 'active', ?, ?, ?, ?, ?)",
            (label, parent_id, note, doc_json, ts, ts),
        )
        new_id = cur.lastrowid
    return get_version(new_id)


def switch_active(version_id: int, now: str | None = None) -> dict[str, Any]:
    """回滚/切换：把活跃指针切到指定版本（含历史归档版本）。"""
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT id, status FROM versions WHERE id = ?", (version_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"版本不存在：{version_id}")
        if row["status"] != "active":
            conn.execute(
                "UPDATE versions SET status = 'archived' WHERE status = 'active'"
            )
            conn.execute(
                "UPDATE versions SET status = 'active', activated_at = ? WHERE id = ?",
                (now or _now(), version_id),
            )
    return get_version(version_id)
