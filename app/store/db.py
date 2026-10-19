"""SQLite 连接与 schema。

数据不出墙：库文件在 data/ 下，已 gitignore，永不进仓库。
环境变量 COMPASS_DB 可覆盖库路径（测试与多部署用）。
"""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = _REPO_ROOT / "data" / "compass.db"


def default_db_path() -> Path:
    """库路径：每次现读环境变量，测试注入才可靠。"""
    env = os.environ.get("COMPASS_DB")
    return Path(env) if env else DEFAULT_DB_PATH


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """打开连接（autocommit；写事务用 transaction() 显式管理）。调用方负责 close()。"""
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """写事务：BEGIN IMMEDIATE 拿写锁，异常回滚。"""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

-- 每行 = 一份完整 OKR 快照。至多一个 active（事务内强制，见 store/versions.py）。
CREATE TABLE IF NOT EXISTS versions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT    NOT NULL,
    status       TEXT    NOT NULL CHECK (status IN ('active', 'archived')),
    parent_id    INTEGER REFERENCES versions(id),
    note         TEXT,
    doc          TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    activated_at TEXT
);

-- 门禁队列：分身写这里，用户批准才派发到真源。
CREATE TABLE IF NOT EXISTS proposals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    action        TEXT    NOT NULL,
    args          TEXT    NOT NULL,
    reason        TEXT    NOT NULL,
    by            TEXT    NOT NULL DEFAULT '分身',
    status        TEXT    NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at    TEXT    NOT NULL,
    decided_at    TEXT,
    decision_note TEXT
);
"""


def init_db() -> None:
    """建表（幂等）。库版本号只在旧库升级时推进。

    注意：executescript 会隐式提交，不能包进显式事务；各语句 autocommit，
    靠幂等保证安全（初始化只在进程内跑一次，见 store/__init__.py）。
    """
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        (count,) = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()
        if count == 0:
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,)
            )
            return
        (version,) = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        if version is not None and version < SCHEMA_VERSION:
            conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
