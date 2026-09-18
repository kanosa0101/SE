from sqlalchemy import inspect, text

from app.db import init_db, make_engine


def test_init_db_adds_provenance_columns_to_v1_papers_table(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'v1.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE papers (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    normalized_title VARCHAR(500) NOT NULL,
                    paper_code VARCHAR(120),
                    abstract TEXT,
                    authors TEXT,
                    conference VARCHAR(10) NOT NULL,
                    year INTEGER NOT NULL,
                    source VARCHAR(40) NOT NULL DEFAULT 'manual',
                    source_url VARCHAR(1000),
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT uq_paper_identity UNIQUE (normalized_title, conference, year)
                )
                """
            )
        )

    init_db(engine)
    init_db(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("papers")}
    assert {"crawled_at", "parser_version"} <= columns

    indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspect(engine).get_indexes("papers")
    }
    assert indexes["ix_papers_conference_year"] == ("conference", "year")
    assert indexes["ix_papers_normalized_title"] == ("normalized_title",)
