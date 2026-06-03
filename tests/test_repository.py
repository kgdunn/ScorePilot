"""Tests for the SQLAlchemy repository, including recursive-CTE lineage."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from scorepilot.db import (
    Base,
    Model,
    SqlModelRepository,
    make_engine,
    make_session_factory,
)


@pytest.fixture
def session() -> Iterator[Session]:
    """An in-memory SQLite session with the schema created."""
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        yield s


def _add(repo: SqlModelRepository, *, parent: Model | None, n: int) -> Model:
    return repo.add(Model(kind="PCA", n_components=n, parent_id=parent.id if parent else None))


def test_add_assigns_id_and_round_trips(session: Session) -> None:
    repo = SqlModelRepository(session)
    model = _add(repo, parent=None, n=2)

    assert model.id is not None
    fetched = repo.get(model.id)
    assert fetched is not None
    assert fetched.kind == "PCA"
    assert fetched.n_components == 2
    assert fetched.parent_id is None
    assert fetched.preprocessing == {}
    assert fetched.excluded_samples == []


def test_get_missing_returns_none(session: Session) -> None:
    repo = SqlModelRepository(session)
    assert repo.get(999) is None


def test_lineage_returns_root_first_chain(session: Session) -> None:
    repo = SqlModelRepository(session)
    root = _add(repo, parent=None, n=2)
    child = _add(repo, parent=root, n=3)
    grandchild = _add(repo, parent=child, n=4)
    # An unrelated branch that must not appear in the lineage.
    _add(repo, parent=root, n=5)

    lineage = repo.lineage(grandchild.id)

    assert [m.id for m in lineage] == [root.id, child.id, grandchild.id]


def test_lineage_of_root_is_just_itself(session: Session) -> None:
    repo = SqlModelRepository(session)
    root = _add(repo, parent=None, n=2)

    assert [m.id for m in repo.lineage(root.id)] == [root.id]


def test_lineage_of_unknown_id_is_empty(session: Session) -> None:
    repo = SqlModelRepository(session)
    assert repo.lineage(12345) == []
