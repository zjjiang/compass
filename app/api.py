"""compass Web API —— 人类入口：极简看板 + 门禁审批。

分工（同 deputy）：人类走这里直写真源（批准/驳回/切版本）；
分身走 MCP 只能 propose。只读端点 + 三个写端点，仅限 localhost。
"""
from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import domain
from .store import ensure_ready, okr, proposals, versions

WEB_DIR = Path(__file__).resolve().parent / "web"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    ensure_ready()
    yield


app = FastAPI(title="compass · OKR 看板", lifespan=_lifespan)


def _guard(fn: Callable[[], Any]) -> Any:
    """DomainError → 400，KeyError → 404，其余原样上抛。"""
    try:
        return fn()
    except domain.DomainError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'")) from e


# ---------- 只读 ----------


@app.get("/api/active")
def get_active() -> Any:
    return _guard(okr.get_active_okr)


@app.get("/api/review")
def get_review() -> Any:
    return _guard(okr.review_active)


@app.get("/api/versions")
def get_versions() -> Any:
    return _guard(versions.list_versions)


@app.get("/api/versions/{version_id}")
def get_version(version_id: int) -> Any:
    return _guard(lambda: versions.get_version(version_id))


@app.get("/api/proposals")
def get_proposals(status: str | None = "pending") -> Any:
    return _guard(lambda: proposals.list_proposals(status=status))


# ---------- 人类写端点（批准 / 驳回 / 切版本） ----------


class RejectBody(BaseModel):
    note: str | None = None


@app.post("/api/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: int) -> Any:
    return _guard(lambda: proposals.approve(proposal_id))


@app.post("/api/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, body: RejectBody | None = None) -> Any:
    note = body.note if body is not None else None
    return _guard(lambda: proposals.reject(proposal_id, note=note))


@app.post("/api/versions/{version_id}/activate")
def activate_version(version_id: int) -> Any:
    return _guard(lambda: versions.switch_active(version_id))


# ---------- 静态看板 ----------


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
