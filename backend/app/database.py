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


# Dictionary to store session factories per engine (keyed by engine identity)
_engine_factories = {}


async def init_db(database_url: str):
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Store session factory per engine to avoid global state conflicts in tests
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    _engine_factories[id(engine)] = session_factory
    return engine


@asynccontextmanager
async def get_session(engine):
    session_factory = _engine_factories[id(engine)]
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
