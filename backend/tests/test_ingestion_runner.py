import pytest
import httpx
import respx
import tempfile
import os
from sqlalchemy import select, func
from app.database import init_db, get_session, HistoricalData
from app.ingestion.runner import run_backfill


@pytest.mark.asyncio
@respx.mock
async def test_run_backfill_ingests_all_sources():
    # Mock external APIs
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json={"data": [
            {"value": "50", "value_classification": "Neutral", "timestamp": "1711497600"},
        ]})
    )
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=[{"date": 1711497600, "tvl": 4e9}])
    )
    respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json={"totalDataChart": [[1711497600, 5e8]]})
    )
    respx.get("https://stablecoins.llama.fi/stablecoincharts/Solana").mock(
        return_value=httpx.Response(200, json=[
            {"date": "1711497600", "totalCirculatingUSD": {"peggedUSD": 3e9}},
        ])
    )

    csv_content = "time,open,high,low,close,#1\n1711497600,185.2,192.1,183.0,190.5,\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        async with httpx.AsyncClient() as client:
            result = await run_backfill(engine, client, sol_csv_path=csv_path)

        assert result["sol_ohlcv"] == 1
        assert result["fear_greed"] == 1
        assert result["tvl"] == 1
        assert result["dex_volume"] == 1
        assert result["stablecoin_supply"] == 1
        await engine.dispose()
    finally:
        os.unlink(csv_path)


@pytest.mark.asyncio
@respx.mock
async def test_run_backfill_idempotent():
    respx.get("https://api.alternative.me/fng/").mock(
        return_value=httpx.Response(200, json={"data": [
            {"value": "50", "value_classification": "Neutral", "timestamp": "1711497600"},
        ]})
    )
    respx.get("https://api.llama.fi/v2/historicalChainTvl/Solana").mock(
        return_value=httpx.Response(200, json=[{"date": 1711497600, "tvl": 4e9}])
    )
    respx.get("https://api.llama.fi/overview/dexs/solana").mock(
        return_value=httpx.Response(200, json={"totalDataChart": [[1711497600, 5e8]]})
    )
    respx.get("https://stablecoins.llama.fi/stablecoincharts/Solana").mock(
        return_value=httpx.Response(200, json=[
            {"date": "1711497600", "totalCirculatingUSD": {"peggedUSD": 3e9}},
        ])
    )

    csv_content = "time,open,high,low,close,#1\n1711497600,185.2,192.1,183.0,190.5,\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv_content)
        csv_path = f.name

    try:
        engine = await init_db("sqlite+aiosqlite:///:memory:")
        async with httpx.AsyncClient() as client:
            await run_backfill(engine, client, sol_csv_path=csv_path)
            result2 = await run_backfill(engine, client, sol_csv_path=csv_path)

        # All should be 0 on second run
        assert all(v == 0 for v in result2.values())
        await engine.dispose()
    finally:
        os.unlink(csv_path)
