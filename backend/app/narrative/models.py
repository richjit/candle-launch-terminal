from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class NarrativeToken(Base):
    __tablename__ = "narrative_tokens"

    address: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(20))
    pair_address: Mapped[str] = mapped_column(String(60))
    narrative: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    mcap: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_original: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_address: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rugcheck_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Narrative(Base):
    __tablename__ = "narratives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    total_volume: Mapped[float] = mapped_column(Float, default=0)
    avg_gain_pct: Mapped[float] = mapped_column(Float, default=0)
    top_token_address: Mapped[str | None] = mapped_column(String(60), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(20), default="emerging")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
