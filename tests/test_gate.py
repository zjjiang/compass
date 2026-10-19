"""门禁测试：propose 扣队列不生效，approve 才派发落地，reject 驳回。"""
from __future__ import annotations

import pytest

from app import domain
from app.store import okr, proposals, versions


def _seed_kr() -> str:
    okr.add_objective_to_active("O1")
    okr.add_key_result_to_active("o-1", "kr1")
    return "kr-1"


def test_propose_goes_to_queue_without_effect(fresh_db):
    kr_id = _seed_kr()
    p = proposals.propose(
        "update_key_result", {"kr_id": kr_id, "progress": 60}, "本周进展到六成", now="2026-10-19T10:00:00"
    )
    assert p["status"] == "pending"
    # 队列里有它，但真源没动
    assert [q["id"] for q in proposals.list_proposals()] == [p["id"]]
    assert okr.get_active_okr()["doc"]["objectives"][0]["key_results"][0]["progress"] == 0


def test_propose_unknown_action_rejected(fresh_db):
    with pytest.raises(domain.DomainError, match="未知提议动作"):
        proposals.propose("drop_database", {}, "想删库", now="now")


def test_propose_missing_required_key_rejected(fresh_db):
    with pytest.raises(domain.DomainError, match="title"):
        proposals.propose("add_objective", {}, "没带标题", now="now")


def test_propose_blank_reason_rejected(fresh_db):
    with pytest.raises(domain.DomainError, match="理由"):
        proposals.propose("add_objective", {"title": "O"}, "  ", now="now")


def test_approve_dispatches_and_marks_approved(fresh_db):
    kr_id = _seed_kr()
    p = proposals.propose(
        "update_key_result", {"kr_id": kr_id, "progress": 60, "junk": "多余键"}, "进展", now="now"
    )
    done = proposals.approve(p["id"], now="2026-10-19T11:00:00")
    assert done["proposal"]["status"] == "approved"
    assert done["result"]["doc"]["objectives"][0]["key_results"][0]["progress"] == 60
    # 真源真的动了
    assert okr.get_active_okr()["doc"]["objectives"][0]["key_results"][0]["progress"] == 60


def test_approve_rule_violation_keeps_proposal_pending(fresh_db):
    p = proposals.propose("switch_active", {"version_id": 9999}, "切个不存在的版本", now="now")
    with pytest.raises(KeyError):
        proposals.approve(p["id"])
    assert proposals.list_proposals()[0]["status"] == "pending"


def test_reject_marks_rejected_without_effect(fresh_db):
    kr_id = _seed_kr()
    p = proposals.propose("update_key_result", {"kr_id": kr_id, "progress": 60}, "进展", now="now")
    rejected = proposals.reject(p["id"], note="先不更新", now="now")
    assert rejected["status"] == "rejected"
    assert rejected["decision_note"] == "先不更新"
    assert okr.get_active_okr()["doc"]["objectives"][0]["key_results"][0]["progress"] == 0


def test_approve_twice_rejected(fresh_db):
    p = proposals.propose("add_objective", {"title": "O2"}, "新目标", now="now")
    proposals.approve(p["id"])
    with pytest.raises(domain.DomainError, match="已处理"):
        proposals.approve(p["id"])


def test_list_proposals_filters_by_status(fresh_db):
    p1 = proposals.propose("add_objective", {"title": "O2"}, "理由", now="now")
    p2 = proposals.propose("add_objective", {"title": "O3"}, "理由", now="now")
    proposals.reject(p1["id"], now="now")
    pending_ids = [q["id"] for q in proposals.list_proposals()]  # 默认只看 pending
    assert pending_ids == [p2["id"]]
    assert len(proposals.list_proposals(status=None)) == 2


def test_gate_snapshot_and_rollback_flow(fresh_db):
    """完整链：改进度 → 打快照 → 切回旧版本，门禁动作全部生效。"""
    kr_id = _seed_kr()
    p1 = proposals.propose("update_key_result", {"kr_id": kr_id, "progress": 80}, "冲刺", now="now")
    proposals.approve(p1["id"])
    old_version_id = versions.get_active()["id"]

    p2 = proposals.propose("create_version", {"label": "2026Q4"}, "季度定稿", now="now")
    proposals.approve(p2["id"])
    assert len(versions.list_versions()) == 2

    p3 = proposals.propose("switch_active", {"version_id": old_version_id}, "回滚", now="now")
    proposals.approve(p3["id"])
    assert versions.get_active()["id"] == old_version_id
