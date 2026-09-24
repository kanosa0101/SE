from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        # WAL 允许读写并发（API 服务与导入脚本同时访问），
        # busy_timeout 让写操作在短暂锁冲突时等待而不是立即报 database is locked。
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    from app.models import BootstrapSource, Paper, PaperKeyword

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
            # 统计接口的查询依赖这些索引；create_all 不会给已存在的表补建
            # 索引，这里按表统一同步。
            preparer = connection.dialect.identifier_preparer
            for model in (Paper, PaperKeyword, BootstrapSource):
                table_name = model.__tablename__
                existing_indexes = {
                    index["name"]
                    for index in inspect(connection).get_indexes(table_name)
                }
                for index in model.__table__.indexes:
                    if index.name in existing_indexes:
                        continue
                    quoted_name = preparer.quote(index.name)
                    quoted_table = preparer.quote(table_name)
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
