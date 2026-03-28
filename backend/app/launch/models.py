from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LaunchToken(Base):
    __tablename__ = "launch_tokens"

    address: Mapped[str] = mapped_column(String(60), primary_key=True)
    pair_address: Mapped[str] = mapped_column(String(60))
    launchpad: Mapped[str] = mapped_column(String(30), index=True)
    dex: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mcap_peak_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    mcap_peak_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    mcap_peak_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    mcap_current: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_peak_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    buys_1h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sells_1h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buys_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sells_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    checkpoint_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class LaunchDailyStats(Base):
    __tablename__ = "launch_daily_stats"
    __table_args__ = (
        UniqueConstraint("date", "launchpad", name="uq_launch_date_launchpad"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    launchpad: Mapped[str] = mapped_column(String(30))
    tokens_created: Mapped[int] = mapped_column(Integer)
    tokens_migrated: Mapped[int] = mapped_column(Integer)
    migration_rate: Mapped[float] = mapped_column(Float)
    median_peak_mcap_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_peak_mcap_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_peak_mcap_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_time_to_peak: Mapped[float | None] = mapped_column(Float, nullable=True)
    survival_rate_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    survival_rate_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    survival_rate_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_buy_sell_ratio_1h: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_launches: Mapped[int] = mapped_column(Integer)
    total_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
