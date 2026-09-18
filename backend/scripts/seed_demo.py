from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app import models  # noqa: F401
from app.config import get_settings
from app.db import init_db, make_engine, session_factory
from app.services.papers import import_csv


def main() -> None:
    data_file = PROJECT_ROOT / "data" / "demo_papers.csv"
    if not data_file.is_file():
        raise SystemExit(f"demo data file not found: {data_file}")

    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_type = session_factory(engine)
    with session_type() as session:
        summary = import_csv(session, data_file.read_bytes())
    engine.dispose()
    print(
        "Seed complete: "
        f"total={summary.total}, created={summary.created}, "
        f"skipped={summary.skipped}, errors={summary.errors}"
    )


if __name__ == "__main__":
    main()
