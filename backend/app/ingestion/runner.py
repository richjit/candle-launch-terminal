import logging

import httpx

from app.ingestion.sol_csv import ingest_sol_csv
from app.ingestion.historical_fng import ingest_fear_greed_history
from app.ingestion.historical_defillama import (
    ingest_tvl_history,
    ingest_dex_volume_history,
    ingest_stablecoin_history,
)
from app.ingestion.technical_factors import compute_vol_regime

logger = logging.getLogger(__name__)


async def run_backfill(
    engine,
    http_client: httpx.AsyncClient,
    sol_csv_path: str = "data/CRYPTO_SOLUSD, 1D_81fb0.csv",
) -> dict[str, int]:
    """Run all historical data ingestion. Idempotent — skips sources already ingested.

    Returns dict of source_name -> rows_inserted.
    """
    logger.info("Starting historical data backfill...")
    results = {}

    results["sol_ohlcv"] = await ingest_sol_csv(engine, sol_csv_path)
    results["fear_greed"] = await ingest_fear_greed_history(engine, http_client)
    results["tvl"] = await ingest_tvl_history(engine, http_client)
    results["dex_volume"] = await ingest_dex_volume_history(engine, http_client)
    results["stablecoin_supply"] = await ingest_stablecoin_history(engine, http_client)

    # Compute technical factors from OHLCV data (must run after sol_csv ingestion)
    results["vol_regime"] = await compute_vol_regime(engine)

    total = sum(results.values())
    if total > 0:
        logger.info(f"Backfill complete: {results}")
    else:
        logger.info("Backfill skipped — all sources already ingested")

    return results
