import pytest


@pytest.fixture()
def fresh_db(tmp_path, monkeypatch):
    """COMPASS_DB 指向临时库并完成初始化，测试之间互不串库。"""
    monkeypatch.setenv("COMPASS_DB", str(tmp_path / "compass.db"))
    from app.store import init_all

    init_all()
