from collections.abc import Generator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    from app.models import Paper

    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        existing_columns = {column["name"] for column in inspect(connection).get_columns("papers")}
        migrations = (
            ("crawled_at", Paper.__table__.c.crawled_at.type),
            ("parser_version", Paper.__table__.c.parser_version.type),
        )
        for column_name, column_type in migrations:
            if column_name not in existing_columns:
                compiled_type = column_type.compile(dialect=connection.dialect)
                connection.execute(
                    text(f"ALTER TABLE papers ADD COLUMN {column_name} {compiled_type}")
                )

        if connection.dialect.name == "sqlite":
            existing_indexes = {
                index["name"]
                for index in inspect(connection).get_indexes(Paper.__tablename__)
            }
            preparer = connection.dialect.identifier_preparer
            for index in Paper.__table__.indexes:
                if index.name in existing_indexes:
                    continue
                quoted_name = preparer.quote(index.name)
                quoted_table = preparer.quote(Paper.__tablename__)
                quoted_columns = ", ".join(preparer.quote(column.name) for column in index.columns)
                connection.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS {quoted_name} "
                        f"ON {quoted_table} ({quoted_columns})"
                    )
                )


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_dependency(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    with factory() as session:
        yield session


runtime_engine = make_engine(get_settings().database_url)
RuntimeSession = session_factory(runtime_engine)


def get_db() -> Generator[Session, None, None]:
    with RuntimeSession() as session:
        yield session
