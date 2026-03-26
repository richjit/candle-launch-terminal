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
from app.routers.health import router as health_router, set_fetchers

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

    # Create fetchers
    dexscreener = DexScreenerFetcher(cache=cache, http_client=http_client, db_engine=db_engine)

    all_fetchers = [dexscreener]
    set_fetchers(all_fetchers)

    # Register scheduled jobs
    register_fetcher_job(dexscreener, settings.fetch_interval_dexscreener)

    # Run initial fetch
    for f in all_fetchers:
        await f.run()

    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
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
