# backend/app/main.py
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache import MemoryCache
from app.config import get_settings
from app.database import init_db
from app.scheduler import scheduler, register_fetcher_job
from app.fetchers.dexscreener import DexScreenerFetcher
from app.fetchers.solana_rpc import SolanaRpcFetcher
from app.fetchers.coingecko import CoinGeckoFetcher
from app.fetchers.defillama import DefiLlamaFetcher
from app.fetchers.fear_greed import FearGreedFetcher
from app.fetchers.google_trends import GoogleTrendsFetcher
from app.routers.health import router as health_router, set_fetchers
from app.routers.pulse_chart import router as chart_router, set_engine as set_chart_engine
from app.routers.pulse_correlations import router as correlations_router, set_correlations
from app.routers.pulse_ecosystem import router as ecosystem_router, set_cache as set_ecosystem_cache, set_engine as set_ecosystem_engine
from app.ingestion.runner import run_backfill
from app.analysis.correlation import compute_correlations
from app.analysis.score_backfill import backfill_scores

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

cache = MemoryCache()
http_client: httpx.AsyncClient | None = None
db_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, db_engine

    # Startup
    settings = get_settings()
    db_engine = await init_db(settings.database_url)
    http_client = httpx.AsyncClient()

    # Run historical data backfill (idempotent)
    await run_backfill(db_engine, http_client)

    # Compute correlations and backfill scores
    correlations = await compute_correlations(db_engine)
    set_correlations(correlations)
    await backfill_scores(db_engine, correlations)

    # Set engine for chart endpoint
    set_chart_engine(db_engine)

    # Create fetchers
    dexscreener = DexScreenerFetcher(cache=cache, http_client=http_client, db_engine=db_engine)
    solana_rpc = SolanaRpcFetcher(cache=cache, http_client=http_client, rpc_url=settings.solana_rpc_url, db_engine=db_engine)
    coingecko = CoinGeckoFetcher(cache=cache, http_client=http_client, api_key=settings.coingecko_api_key, db_engine=db_engine)
    defillama = DefiLlamaFetcher(cache=cache, http_client=http_client, db_engine=db_engine)
    fear_greed = FearGreedFetcher(cache=cache, http_client=http_client, db_engine=db_engine)
    google_trends = GoogleTrendsFetcher(cache=cache, http_client=http_client, db_engine=db_engine)

    all_fetchers = [dexscreener, solana_rpc, coingecko, defillama, fear_greed, google_trends]
    set_fetchers(all_fetchers)
    set_ecosystem_cache(cache)
    set_ecosystem_engine(db_engine)

    # Register scheduled jobs
    register_fetcher_job(dexscreener, settings.fetch_interval_dexscreener)
    register_fetcher_job(solana_rpc, settings.fetch_interval_rpc)
    register_fetcher_job(coingecko, settings.fetch_interval_coingecko)
    register_fetcher_job(defillama, settings.fetch_interval_defillama)
    register_fetcher_job(fear_greed, settings.fetch_interval_fear_greed)
    register_fetcher_job(google_trends, settings.fetch_interval_google_trends)

    # Run initial fetch
    for f in all_fetchers:
        await f.run()

    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown(wait=True)
    await http_client.aclose()
    await db_engine.dispose()


app = FastAPI(title="Candle Launch Terminal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chart_router)
app.include_router(correlations_router)
app.include_router(ecosystem_router)
