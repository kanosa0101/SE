import importlib.util

from sqlalchemy import func, select

from app.config import Settings
from app.db import init_db, make_engine, session_factory
from app.models import Paper


def test_settings_expose_bootstrap_data_configuration():
    assert "bootstrap_files" in Settings.model_fields
    settings = Settings(bootstrap_files="first.csv,second.csv")

    assert settings.bootstrap_files == "first.csv,second.csv"


def test_bootstrap_imports_multiple_files_once(tmp_path):
    module_spec = importlib.util.find_spec("app.services.bootstrap")
    assert module_spec is not None
    from app.services.bootstrap import bootstrap_database

    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    first.write_text(
        "title,conference,year,keywords\n"
        "First Bootstrap Paper,CVPR,2024,detection\n",
        encoding="utf-8",
    )
    second.write_text(
        "title,conference,year,keywords\n"
        "Second Bootstrap Paper,ICCV,2023,segmentation\n",
        encoding="utf-8",
    )
    engine = make_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    init_db(engine)

    assert bootstrap_database(engine, [first, second]) is True
    with session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(Paper)) == 2

    assert bootstrap_database(engine, [first, second]) is False
    with session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(Paper)) == 2
