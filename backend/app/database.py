# backend/app/database.py
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, Integer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MetricData(Base):
    __tablename__ = "metric_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


# Global session factory, initialized by init_db
_session_factory = None


async def init_db(database_url: str):
    global _session_factory
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Create session factory once and reuse for all sessions
    _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine


@asynccontextmanager
async def get_session(engine):
    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
