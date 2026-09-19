from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import models  # noqa: F401
from app.config import get_settings
from app.db import init_db, make_engine, session_factory
from app.models import Keyword, Paper, PaperKeyword
from app.services.papers import _replace_keywords
from sqlalchemy import text


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_type = session_factory(engine)
    rebuilt = 0
    skipped = 0
    with session_type() as session:
        papers = session.query(Paper).all()
        for paper in papers:
            links = (
                session.query(PaperKeyword)
                .filter(PaperKeyword.paper_id == paper.id)
                .all()
            )
            # 只重建机器提取的关键词；用户提供的关键词保持原样。
            if any(link.method != "tfidf" for link in links):
                skipped += 1
                continue
            _replace_keywords(session, paper, [])
            rebuilt += 1
        # 先落库本轮重建的关联，再用 SQL 判断真孤儿，避免 autoflush 关闭时误判。
        session.flush()
        orphan_ids = [
            row[0]
            for row in session.execute(
                text(
                    "SELECT k.id FROM keywords k WHERE NOT EXISTS "
                    "(SELECT 1 FROM paper_keywords pk WHERE pk.keyword_id = k.id)"
                )
            ).all()
        ]
        if orphan_ids:
            session.query(Keyword).filter(Keyword.id.in_(orphan_ids)).delete(
                synchronize_session=False
            )
        session.commit()
        total = session.query(Paper).count()
        keyword_count = session.query(Keyword).count()
    engine.dispose()
    print(
        "Re-extract complete: "
        f"papers={total}, rebuilt={rebuilt}, skipped(provided)={skipped}, "
        f"keywords={keyword_count}, orphan_removed={len(orphan_ids)}"
    )


if __name__ == "__main__":
    main()
