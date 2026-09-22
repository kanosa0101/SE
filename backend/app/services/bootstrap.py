import logging
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import Engine, func, select

from app.db import session_factory
from app.models import Paper
from app.services.papers import import_csv


LOGGER = logging.getLogger(__name__)


def bootstrap_database(engine: Engine, files: Sequence[Path]) -> bool:
    paths = [Path(path) for path in files]
    if not paths:
        return False

    with session_factory(engine)() as session:
        existing = session.scalar(select(func.count()).select_from(Paper)) or 0
        if existing:
            LOGGER.info("Database already contains %s papers; skip bootstrap", existing)
            return False

        missing = [path for path in paths if not path.is_file()]
        if missing:
            missing_text = ", ".join(str(path) for path in missing)
            raise FileNotFoundError(f"bootstrap data file not found: {missing_text}")

        for path in paths:
            summary = import_csv(session, path.read_bytes(), strict=True)
            LOGGER.info(
                "Bootstrapped %s: total=%s created=%s skipped=%s errors=%s",
                path,
                summary.total,
                summary.created,
                summary.skipped,
                summary.errors,
            )

    return True
