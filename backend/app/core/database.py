from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.rls import current as rls_current

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@event.listens_for(engine.sync_engine, "begin")
def _apply_rls(conn) -> None:
    # The pool hands back the login role. A superuser ignores row-level security,
    # so that connection becomes fsp_app for the transaction. Production logs in
    # as fsp_app already, and this branch does not run.
    is_super = conn.execute(text(
        "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    )).scalar()
    if is_super:
        conn.execute(text("SET SESSION AUTHORIZATION fsp_app"))
    scope = rls_current()
    conn.execute(text(
        "SELECT set_config('app.bypass_rls', :bypass, true), "
        "set_config('app.participant_id', :participant, true), "
        "set_config('app.employer_id', :employer, true)"
    ), {
        "bypass": "on" if scope.get("bypass") else "",
        "participant": scope.get("participant_id") or "",
        "employer": scope.get("employer_id") or "",
    })


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
