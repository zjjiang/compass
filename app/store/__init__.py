"""store 包：真源读写。入口 init_all()，MCP / Web / 测试统一走它。"""
from __future__ import annotations

from pathlib import Path

_initialized_for: Path | None = None


def init_all() -> None:
    """建库 + 空库自举一个活跃版本（幂等）。"""
    from . import db, versions

    db.init_db()
    with db.transaction() as conn:
        versions.ensure_initial_version(conn)


def ensure_ready() -> None:
    """惰性初始化：库路径变过（如测试换 env）就重建。MCP 工具与 API 入口先调它。"""
    global _initialized_for
    from . import db

    path = db.default_db_path()
    if _initialized_for != path:
        init_all()
        _initialized_for = path
