"""版本层测试：快照、唯一活跃、回滚、归档只读。"""
from __future__ import annotations

import pytest

from app import domain
from app.store import versions


def test_empty_db_bootstraps_one_active_version(fresh_db):
    active = versions.get_active()
    assert active["status"] == "active"
    assert active["label"] == "初始版本"
    assert active["doc"] == {"objectives": []}


def test_create_version_snapshots_active_and_activates_new(fresh_db):
    old = versions.get_active()

    new = versions.create_version("2026Q4", note="第四季度", now="2026-10-19T10:00:00")

    assert new["status"] == "active"
    assert new["label"] == "2026Q4"
    assert new["parent_id"] == old["id"]
    assert new["doc"] == old["doc"]  # 快照复制
    assert versions.get_active()["id"] == new["id"]
    archived = versions.get_version(old["id"])
    assert archived["status"] == "archived"


def test_create_version_blank_starts_empty_doc(fresh_db):
    new = versions.create_version("从零开始", copy_active=False)
    assert new["doc"] == {"objectives": []}


def test_only_one_active_ever(fresh_db):
    v1 = versions.create_version("v1")
    v2 = versions.create_version("v2")
    v3 = versions.create_version("v3")
    actives = [v for v in versions.list_versions() if v["status"] == "active"]
    assert [v["id"] for v in actives] == [v3["id"]]
    # create_version 返回的是创建时刻的状态（active），归档与否以现读为准
    assert versions.get_version(v1["id"])["status"] == "archived"
    assert versions.get_version(v2["id"])["status"] == "archived"


def test_switch_active_rolls_back_to_history(fresh_db):
    v1 = versions.get_active()
    v2 = versions.create_version("v2")

    switched = versions.switch_active(v1["id"])

    assert switched["id"] == v1["id"]
    assert versions.get_active()["id"] == v1["id"]
    assert versions.get_version(v2["id"])["status"] == "archived"
    # 回滚不丢历史：v2 仍可再切回去
    versions.switch_active(v2["id"])
    assert versions.get_active()["id"] == v2["id"]


def test_switch_active_to_current_is_noop(fresh_db):
    active = versions.get_active()
    switched = versions.switch_active(active["id"])
    assert switched["id"] == active["id"]
    assert versions.get_active()["id"] == active["id"]


def test_switch_active_unknown_version_raises(fresh_db):
    with pytest.raises(KeyError):
        versions.switch_active(9999)


def test_get_version_unknown_raises(fresh_db):
    with pytest.raises(KeyError):
        versions.get_version(9999)


def test_list_versions_newest_first(fresh_db):
    versions.create_version("v1")
    versions.create_version("v2", note="备注")
    rows = versions.list_versions()
    assert len(rows) == 3
    assert [r["label"] for r in rows[:2]] == ["v2", "v1"]
    assert rows[0]["note"] == "备注"


def test_create_version_requires_label(fresh_db):
    with pytest.raises(domain.DomainError):
        versions.create_version("   ")
