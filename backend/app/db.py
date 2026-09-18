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
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        existing_columns = {column["name"] for column in inspect(connection).get_columns("papers")}
        migrations = (
            ("crawled_at", "DATETIME"),
            ("parser_version", "VARCHAR(40)"),
        )
        for column_name, column_type in migrations:
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE papers ADD COLUMN {column_name} {column_type}"))


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
