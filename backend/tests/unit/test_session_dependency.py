from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.api import deps
from fastapi import Request
from sqlalchemy.orm import Session


class FakeSession:
    def __init__(self, *, commit_error: Exception | None = None) -> None:
        self.commit_error = commit_error
        self.events: list[str] = []

    def commit(self) -> None:
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self) -> None:
        self.events.append("rollback")

    def close(self) -> None:
        self.events.append("close")


def request() -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/receipts",
            "raw_path": b"/api/v1/receipts",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "state": {},
        }
    )


def test_commit_failure_rolls_back_and_runs_storage_cleanup(monkeypatch) -> None:
    session = FakeSession(commit_error=RuntimeError("commit failed"))
    monkeypatch.setattr(deps, "get_session_factory", lambda: lambda: session)
    req = request()
    cleaned: list[str] = []
    req.state.rollback_callbacks = [lambda: cleaned.append("receipt-object")]
    dependency: Iterator[Session] = deps.get_session(req)

    assert next(dependency) is session
    with pytest.raises(RuntimeError, match="commit failed"):
        next(dependency)

    assert session.events == ["commit", "rollback", "close"]
    assert cleaned == ["receipt-object"]
    assert req.state.rollback_callbacks == []


def test_successful_commit_discards_storage_cleanup(monkeypatch) -> None:
    session = FakeSession()
    monkeypatch.setattr(deps, "get_session_factory", lambda: lambda: session)
    req = request()
    req.state.rollback_callbacks = [lambda: pytest.fail("cleanup ran after commit")]
    dependency: Iterator[Session] = deps.get_session(req)

    next(dependency)
    with pytest.raises(StopIteration):
        next(dependency)

    assert session.events == ["commit", "close"]
    assert req.state.rollback_callbacks == []
