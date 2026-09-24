import logging
from hashlib import sha256
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import Engine, func, select

from app.db import session_factory
from app.models import BootstrapSource, Paper
from app.services.papers import import_csv


LOGGER = logging.getLogger(__name__)


def bootstrap_database(engine: Engine, files: Sequence[Path]) -> bool:
    paths = [Path(path) for path in files]
    if not paths:
        return False

    missing = [path for path in paths if not path.is_file()]
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"bootstrap data file not found: {missing_text}")

    imported_any = False
    with session_factory(engine)() as session:
        existing = session.scalar(select(func.count()).select_from(Paper)) or 0
        if existing:
            LOGGER.info("Database already contains %s papers; checking for new bootstrap sources", existing)

        for path in paths:
            content = path.read_bytes()
            content_hash = sha256(content).hexdigest()
            if session.get(BootstrapSource, content_hash) is not None:
                continue

            summary = import_csv(session, content, strict=True)
            session.add(BootstrapSource(content_hash=content_hash, file_name=path.name))
            session.commit()
            imported_any = True
            LOGGER.info(
                "Bootstrapped %s: total=%s created=%s skipped=%s errors=%s",
                path,
                summary.total,
                summary.created,
                summary.skipped,
                summary.errors,
            )

    return imported_any
