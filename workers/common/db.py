from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.config import settings
from common.models import Base

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def update_heartbeat(worker_name: str, status: str, details: dict | None = None) -> None:
    from datetime import UTC, datetime

    from common.models import WorkerHeartbeat

    try:
        with session_scope() as db:
            heartbeat = db.get(WorkerHeartbeat, worker_name)
            if heartbeat is None:
                heartbeat = WorkerHeartbeat(worker_name=worker_name)
                db.add(heartbeat)
            heartbeat.status = status
            heartbeat.last_seen_at = datetime.now(UTC)
            heartbeat.details = details or {}
    except Exception:
        pass
