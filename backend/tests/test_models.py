import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base, init_db
from app.models import Paper


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_paper_persists_required_metadata(db_session):
    paper = Paper(
        title="A Test Vision Paper",
        conference="CVPR",
        year=2024,
        source="demo",
        source_url="https://example.test/paper",
    )
    db_session.add(paper)
    db_session.commit()

    loaded = db_session.query(Paper).one()

    assert loaded.conference == "CVPR"
    assert loaded.year == 2024
