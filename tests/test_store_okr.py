"""OKR 编辑层测试：纯函数变换 + 活跃版本落库。"""
from __future__ import annotations

import pytest

from app import domain
from app.store import okr, versions

# ---------- 纯函数变换（不碰库） ----------


def test_add_objective_assigns_sequential_ids():
    doc = okr.add_objective(okr.EMPTY_DOC, "把 deputy 做成日活系统")
    doc = okr.add_objective(doc, "减脂到 78kg", note="年内")
    assert [o["id"] for o in doc["objectives"]] == ["o-1", "o-2"]
    assert doc["objectives"][1]["note"] == "年内"
    assert doc["objectives"][0]["key_results"] == []


def test_add_objective_rejects_blank_title():
    with pytest.raises(domain.DomainError):
        okr.add_objective(okr.EMPTY_DOC, "  ")


def test_update_and_remove_objective():
    doc = okr.add_objective(okr.EMPTY_DOC, "旧标题")
    doc = okr.update_objective(doc, "o-1", title="新标题", note="备注")
    assert doc["objectives"][0]["title"] == "新标题"
    doc = okr.remove_objective(doc, "o-1")
    assert doc["objectives"] == []


def test_update_missing_objective_raises():
    with pytest.raises(domain.DomainError, match="o-9"):
        okr.update_objective(okr.EMPTY_DOC, "o-9", title="x")


def test_add_key_result_and_progress():
    doc = okr.add_objective(okr.EMPTY_DOC, "O")
    doc = okr.add_key_result(doc, "o-1", "每周回顾 1 次")
    doc = okr.update_key_result(doc, "kr-1", progress=40)
    kr = doc["objectives"][0]["key_results"][0]
    assert kr["progress"] == 40


def test_add_key_result_to_missing_objective_raises():
    with pytest.raises(domain.DomainError, match="o-9"):
        okr.add_key_result(okr.EMPTY_DOC, "o-9", "kr")


def test_update_key_result_progress_bounds():
    doc = okr.add_objective(okr.EMPTY_DOC, "O")
    doc = okr.add_key_result(doc, "o-1", "kr")
    with pytest.raises(domain.DomainError, match="0-100"):
        okr.update_key_result(doc, "kr-1", progress=120)
    with pytest.raises(domain.DomainError, match="progress"):
        okr.update_key_result(doc, "kr-1", progress="一半")


def test_remove_key_result_and_missing_kr():
    doc = okr.add_objective(okr.EMPTY_DOC, "O")
    doc = okr.add_key_result(doc, "o-1", "kr")
    doc = okr.remove_key_result(doc, "kr-1")
    assert doc["objectives"][0]["key_results"] == []
    with pytest.raises(domain.DomainError, match="kr-9"):
        okr.remove_key_result(doc, "kr-9")


def test_remove_objective_cascades_key_results():
    doc = okr.add_objective(okr.EMPTY_DOC, "O")
    doc = okr.add_key_result(doc, "o-1", "kr1")
    doc = okr.add_objective(doc, "O2")
    doc = okr.remove_objective(doc, "o-1")
    assert doc["objectives"] == [{"id": "o-2", "title": "O2", "note": None, "key_results": []}]


def test_summarize():
    doc = okr.add_objective(okr.EMPTY_DOC, "O1")
    doc = okr.add_key_result(doc, "o-1", "kr1")
    doc = okr.update_key_result(doc, "kr-1", progress=50)
    doc = okr.add_key_result(doc, "o-1", "kr2")
    doc = okr.add_objective(doc, "O2")
    summary = okr.summarize(doc)
    assert summary["objective_count"] == 2
    assert summary["kr_count"] == 2
    assert summary["overall_progress"] == 25  # (50+0)/2


# ---------- 落库（只动活跃版本，归档只读） ----------


def test_add_objective_persists_to_active_version(fresh_db):
    result = okr.add_objective_to_active("O1")
    ids = [o["id"] for o in result["doc"]["objectives"]]
    assert ids == ["o-1"]
    assert versions.get_active()["doc"]["objectives"][0]["title"] == "O1"


def test_edits_never_touch_archived_snapshots(fresh_db):
    okr.add_objective_to_active("O1")
    okr.add_key_result_to_active("o-1", "kr1")
    snapshot_id = versions.create_version("快照")["parent_id"]  # 被归档的旧活跃
    assert versions.get_version(snapshot_id)["status"] == "archived"

    okr.add_objective_to_active("新目标")  # 只动新活跃版本

    archived = versions.get_version(snapshot_id)
    assert archived["status"] == "archived"
    assert [o["title"] for o in archived["doc"]["objectives"]] == ["O1"]


def test_get_active_okr_summary(fresh_db):
    okr.add_objective_to_active("O1")
    okr.add_key_result_to_active("o-1", "kr1")
    result = okr.get_active_okr()
    assert result["summary"]["kr_count"] == 1
    assert result["summary"]["overall_progress"] == 0


def test_review_shape(fresh_db):
    okr.add_objective_to_active("O1")
    okr.add_key_result_to_active("o-1", "kr1")
    okr.update_key_result_on_active("kr-1", progress=100)
    result = okr.review_active()
    assert result["version"]["label"] == "初始版本"
    assert result["overall_progress"] == 100
    assert result["objectives"][0]["avg_progress"] == 100
    assert result["krs_done"] == 1
    assert result["krs_not_started"] == 0
