"""OKR 编辑层 —— 结构化操作活跃版本的 doc。

分两层：
  - 纯函数变换（add/update/remove …）：吃 doc 吐新 doc，不碰库，直接单测。
  - *_to_active / get_active_okr / review：落库包装，只动活跃版本（归档只读）。
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .. import domain
from . import db, versions

EMPTY_DOC: dict[str, Any] = versions.EMPTY_DOC


# ---------- 纯函数变换（doc → 新 doc） ----------


def _next_id(doc: dict[str, Any], prefix: str) -> str:
    """现有 id 后缀最大值 + 1，如 o-1、o-2…（kr 同理全局编号）。"""
    used = [0]
    for objective in doc.get("objectives", []):
        for key in ("id",):
            if str(objective.get(key, "")).startswith(f"{prefix}-"):
                used.append(int(objective[key].split("-")[1]))
        for kr in objective.get("key_results", []):
            if str(kr.get("id", "")).startswith(f"{prefix}-"):
                used.append(int(kr["id"].split("-")[1]))
    return f"{prefix}-{max(used) + 1}"


def _objective(doc: dict[str, Any], objective_id: str) -> dict[str, Any]:
    for objective in doc.get("objectives", []):
        if objective["id"] == objective_id:
            return objective
    raise domain.DomainError(f"目标不存在：{objective_id}")


def _find_kr(doc: dict[str, Any], kr_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for objective in doc.get("objectives", []):
        for kr in objective.get("key_results", []):
            if kr["id"] == kr_id:
                return objective, kr
    raise domain.DomainError(f"关键结果不存在：{kr_id}")


def add_objective(
    doc: dict[str, Any], title: str, note: str | None = None
) -> dict[str, Any]:
    title = domain.validate_title(title)
    objectives = list(doc.get("objectives", []))
    new_objective = {
        "id": _next_id(doc, "o"),
        "title": title,
        "note": note,
        "key_results": [],
    }
    return {**doc, "objectives": [*objectives, new_objective]}


def update_objective(
    doc: dict[str, Any],
    objective_id: str,
    *,
    title: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    objectives = [
        {
            **o,
            **({"title": domain.validate_title(title)} if title is not None else {}),
            **({"note": note} if note is not None else {}),
        }
        if o["id"] == objective_id
        else o
        for o in doc.get("objectives", [])
    ]
    if all(o["id"] != objective_id for o in objectives):
        raise domain.DomainError(f"目标不存在：{objective_id}")
    return {**doc, "objectives": objectives}


def remove_objective(doc: dict[str, Any], objective_id: str) -> dict[str, Any]:
    _objective(doc, objective_id)  # 不存在则报错
    return {
        **doc,
        "objectives": [o for o in doc.get("objectives", []) if o["id"] != objective_id],
    }


def add_key_result(
    doc: dict[str, Any], objective_id: str, title: str, note: str | None = None
) -> dict[str, Any]:
    title = domain.validate_title(title)
    found = _objective(doc, objective_id)
    new_kr = {
        "id": _next_id(doc, "kr"),
        "title": title,
        "progress": 0,
        "note": note,
    }
    updated = {**found, "key_results": [*found.get("key_results", []), new_kr]}
    return {**doc, "objectives": [updated if o["id"] == objective_id else o for o in doc.get("objectives", [])]}


def update_key_result(
    doc: dict[str, Any],
    kr_id: str,
    *,
    title: str | None = None,
    progress: float | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    _find_kr(doc, kr_id)  # 不存在则报错
    patch: dict[str, Any] = {}
    if title is not None:
        patch["title"] = domain.validate_title(title)
    if progress is not None:
        patch["progress"] = domain.validate_progress(progress)
    if note is not None:
        patch["note"] = note

    def patch_kr(kr: dict[str, Any]) -> dict[str, Any]:
        return {**kr, **patch} if kr["id"] == kr_id else kr

    objectives = [
        {**o, "key_results": [patch_kr(kr) for kr in o.get("key_results", [])]}
        for o in doc.get("objectives", [])
    ]
    return {**doc, "objectives": objectives}


def remove_key_result(doc: dict[str, Any], kr_id: str) -> dict[str, Any]:
    _find_kr(doc, kr_id)  # 不存在则报错
    objectives = [
        {
            **o,
            "key_results": [kr for kr in o.get("key_results", []) if kr["id"] != kr_id],
        }
        for o in doc.get("objectives", [])
    ]
    return {**doc, "objectives": objectives}


# ---------- 汇总（纯函数） ----------


def _all_krs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [kr for o in doc.get("objectives", []) for kr in o.get("key_results", [])]


def summarize(doc: dict[str, Any]) -> dict[str, Any]:
    krs = _all_krs(doc)
    overall = round(sum(kr["progress"] for kr in krs) / len(krs)) if krs else 0
    return {
        "objective_count": len(doc.get("objectives", [])),
        "kr_count": len(krs),
        "overall_progress": overall,
    }


def review(doc: dict[str, Any]) -> dict[str, Any]:
    """轻量回顾：各 O 的 KR 均分进度 + 完成/未启动计数。"""
    per_objective = []
    for o in doc.get("objectives", []):
        krs = o.get("key_results", [])
        avg = round(sum(kr["progress"] for kr in krs) / len(krs)) if krs else 0
        per_objective.append({"id": o["id"], "title": o["title"], "avg_progress": avg, "kr_count": len(krs)})
    krs = _all_krs(doc)
    return {
        "overall_progress": summarize(doc)["overall_progress"],
        "objective_count": len(doc.get("objectives", [])),
        "kr_count": len(krs),
        "krs_done": sum(1 for kr in krs if kr["progress"] >= domain.MAX_PROGRESS),
        "krs_not_started": sum(1 for kr in krs if kr["progress"] <= domain.MIN_PROGRESS),
        "objectives": per_objective,
    }


# ---------- 落库包装（只动活跃版本） ----------


def _mutate_active(transform) -> sqlite3.Row:
    """在事务内对活跃版本 doc 施加纯函数变换并写回。"""
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT id, doc FROM versions WHERE status = 'active' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise domain.DomainError("没有活跃版本，库状态异常")
        new_doc = transform(json.loads(row["doc"]))
        conn.execute(
            "UPDATE versions SET doc = ? WHERE id = ?",
            (json.dumps(new_doc, ensure_ascii=False), row["id"]),
        )
    return row


def get_active_okr() -> dict[str, Any]:
    active = versions.get_active()
    return {**active, "summary": summarize(active["doc"])}


def add_objective_to_active(title: str, note: str | None = None) -> dict[str, Any]:
    _mutate_active(lambda doc: add_objective(doc, title, note))
    return get_active_okr()


def update_objective_on_active(
    objective_id: str, *, title: str | None = None, note: str | None = None
) -> dict[str, Any]:
    _mutate_active(lambda doc: update_objective(doc, objective_id, title=title, note=note))
    return get_active_okr()


def remove_objective_on_active(objective_id: str) -> dict[str, Any]:
    _mutate_active(lambda doc: remove_objective(doc, objective_id))
    return get_active_okr()


def add_key_result_to_active(
    objective_id: str, title: str, note: str | None = None
) -> dict[str, Any]:
    _mutate_active(lambda doc: add_key_result(doc, objective_id, title, note))
    return get_active_okr()


def update_key_result_on_active(
    kr_id: str,
    *,
    title: str | None = None,
    progress: float | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    _mutate_active(
        lambda doc: update_key_result(doc, kr_id, title=title, progress=progress, note=note)
    )
    return get_active_okr()


def remove_key_result_on_active(kr_id: str) -> dict[str, Any]:
    _mutate_active(lambda doc: remove_key_result(doc, kr_id))
    return get_active_okr()


def review_active() -> dict[str, Any]:
    active = versions.get_active()
    return {"version": {"id": active["id"], "label": active["label"]}, **review(active["doc"])}
