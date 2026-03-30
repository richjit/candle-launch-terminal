"""
Dune Analytics ingestion — fetches on-chain Solana metrics via saved queries
and inline SQL.

Metrics:
- new_wallets: Daily count of wallets making their first-ever transaction
- priority_fees: Daily median priority fee in SOL
- pumpfun_creates: Daily count of new tokens created on pump.fun

Uses saved queries (by ID) and inline SQL (via /api/v1/sql/execute).
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import httpx
from sqlalchemy import select, func

from app.database import get_session, HistoricalData

logger = logging.getLogger(__name__)

DUNE_API_BASE = "https://api.dune.com/api/v1"

# Saved query IDs on dune.com
QUERY_IDS = {
    "new_wallets": 6916611,
    "priority_fees": 6916620,
}


def _get_api_key() -> str | None:
    key = os.environ.get("DUNE_API_KEY")
    if key:
        return key
    try:
        from app.config import get_settings
        key = get_settings().dune_api_key
        return key if key else None
    except Exception:
        return None


async def _execute_and_poll(
    http_client: httpx.AsyncClient,
    api_key: str,
    query_id: int,
    timeout_seconds: int = 300,
    poll_interval: int = 10,
) -> list[dict] | None:
    """Execute a saved Dune query by ID and poll for results."""
    headers = {"X-Dune-API-Key": api_key}

    # Execute
    resp = await http_client.post(
        f"{DUNE_API_BASE}/query/{query_id}/execute",
        headers=headers,
        json={},
        timeout=30.0,
    )
    if resp.status_code != 200:
        logger.error(f"Dune execute failed for query {query_id}: {resp.status_code} {resp.text[:200]}")
        return None

    execution_id = resp.json().get("execution_id")
    if not execution_id:
        logger.error(f"No execution_id for query {query_id}")
        return None

    logger.info(f"Dune query {query_id} submitted, execution_id={execution_id}")

    # Poll for results
    elapsed = 0
    while elapsed < timeout_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        resp = await http_client.get(
            f"{DUNE_API_BASE}/execution/{execution_id}/results",
            headers=headers,
            timeout=30.0,
        )
        if resp.status_code != 200:
            logger.warning(f"Dune poll error: {resp.status_code}")
            continue

        result = resp.json()
        state = result.get("state")

        if state == "QUERY_STATE_COMPLETED":
            rows = result.get("result", {}).get("rows", [])
            logger.info(f"Dune query {query_id} completed: {len(rows)} rows")
            return rows
        elif state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
            error = result.get("error", "unknown")
            logger.error(f"Dune query {query_id} {state}: {error}")
            return None
        else:
            logger.debug(f"Dune query {query_id}: {state} ({elapsed}s elapsed)")

    logger.error(f"Dune query {query_id} timed out after {timeout_seconds}s")
    return None


# Daily token creates per launchpad — from adam_tehc's memecoin-wars dashboard.
# Covers: PumpFun, LetsBonk, Bags, Moonshot, Boop, Believe, LaunchLab, Wavebreak, Jup Studio.
LAUNCHPAD_CREATES_SQL = """\
WITH
pumpdotfun_tokens_old AS (
  SELECT MIN(block_time) AS time, token_mint_address, 'Pumpdotfun' AS platform
  FROM tokens_solana.transfers
  WHERE action = 'mint'
    AND outer_executing_account = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    AND block_time >= CURRENT_DATE - INTERVAL '120' DAY
    AND block_time < DATE '2025-11-13'
  GROUP BY token_mint_address
),
pumpdotfun_tokens_new AS (
  SELECT MIN(block_time) AS time, account_arguments[1] AS token_mint_address, 'Pumpdotfun' AS platform
  FROM solana.instruction_calls
  WHERE bytearray_substring(data, 1, 7) = 0xd6904cec5f8b31
    AND executing_account = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    AND outer_executing_account = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    AND tx_success = true
    AND block_time >= DATE '2025-11-13'
    AND block_time >= CURRENT_DATE - INTERVAL '120' DAY
  GROUP BY account_arguments[1]
),
mint_transfers AS (
  SELECT block_time, token_mint_address, outer_executing_account, tx_signer, inner_instruction_index
  FROM tokens_solana.transfers
  WHERE block_time >= CURRENT_DATE - INTERVAL '120' DAY
    AND action = 'mint'
    AND outer_executing_account IN (
      'MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG',
      'boop8hVGQGqehUK2iVEMEnMrL5RbjywRzHKBmBE7ry4',
      'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    )
),
xfer_tokens AS (
  SELECT MIN(time) AS time, token_mint_address, platform
  FROM (
    SELECT block_time AS time, token_mint_address,
      CASE
        WHEN outer_executing_account = 'MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG' THEN NULL
        WHEN outer_executing_account = 'boop8hVGQGqehUK2iVEMEnMrL5RbjywRzHKBmBE7ry4' AND inner_instruction_index = 4 THEN 'Boop'
        WHEN outer_executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND tx_signer = 'BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv' THEN 'Bags'
        WHEN outer_executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND tx_signer = '7rtiKSUDLBm59b1SBmD9oajcP8xE64vAGSMbAN5CXy1q' THEN 'Moonshot'
      END AS platform
    FROM mint_transfers
    WHERE outer_executing_account = 'MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG'
      OR (outer_executing_account = 'boop8hVGQGqehUK2iVEMEnMrL5RbjywRzHKBmBE7ry4' AND inner_instruction_index = 4)
      OR (outer_executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
          AND tx_signer IN ('BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv','7rtiKSUDLBm59b1SBmD9oajcP8xE64vAGSMbAN5CXy1q'))
  ) s WHERE platform IS NOT NULL
  GROUP BY token_mint_address, platform
),
calls_filtered AS (
  SELECT block_time, tx_id, executing_account, tx_signer, account_arguments, inner_instructions, data
  FROM solana.instruction_calls
  WHERE block_time >= CURRENT_DATE - INTERVAL '120' DAY
    AND tx_success = TRUE
    AND executing_account IN (
      'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj',
      'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN',
      'waveQX2yP3H1pVU8djGvEHmYg8uamQ84AuyGtpsrXTF'
    )
),
call_tokens AS (
  SELECT MIN(time) AS time, token_mint_address, platform
  FROM (
    SELECT block_time AS time,
      CASE
        WHEN executing_account = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj' AND (varbinary_starts_with(data, 0xafaf6d1f0d989bed) OR varbinary_starts_with(data, 0x4399af27)) THEN account_arguments[7]
        WHEN executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND tx_signer = '5qWya6UjwWnGVhdSBL3hyZ7B45jbk6Byt1hwd7ohEGXE' AND varbinary_starts_with(data, 0x8c55d7b0) THEN account_arguments[4]
        WHEN executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND cardinality(account_arguments) >= 9 AND account_arguments[9] = '8rE9CtCjwhSmbwL5fbJBtRFsS3ohfMcDFeTTC7t4ciUA' THEN tx_id
        WHEN executing_account = 'waveQX2yP3H1pVU8djGvEHmYg8uamQ84AuyGtpsrXTF' AND cardinality(inner_instructions) > 0 AND inner_instructions[1].data = '11114XtYk9gGfZoo968fyjNUYQJKf9gdmkGoaoBpzFv4vyaSMBn3VKxZdv7mZLzoyX5YNC' THEN account_arguments[3]
      END AS token_mint_address,
      CASE
        WHEN executing_account = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj' AND (varbinary_starts_with(data, 0xafaf6d1f0d989bed) OR varbinary_starts_with(data, 0x4399af27)) THEN 'LetsBonk'
        WHEN executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND tx_signer = '5qWya6UjwWnGVhdSBL3hyZ7B45jbk6Byt1hwd7ohEGXE' AND varbinary_starts_with(data, 0x8c55d7b0) THEN 'Believe'
        WHEN executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND cardinality(account_arguments) >= 9 AND account_arguments[9] = '8rE9CtCjwhSmbwL5fbJBtRFsS3ohfMcDFeTTC7t4ciUA' THEN 'JupStudio'
        WHEN executing_account = 'waveQX2yP3H1pVU8djGvEHmYg8uamQ84AuyGtpsrXTF' AND cardinality(inner_instructions) > 0 AND inner_instructions[1].data = '11114XtYk9gGfZoo968fyjNUYQJKf9gdmkGoaoBpzFv4vyaSMBn3VKxZdv7mZLzoyX5YNC' THEN 'Wavebreak'
      END AS platform
    FROM calls_filtered
    WHERE (executing_account = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj' AND (varbinary_starts_with(data, 0xafaf6d1f0d989bed) OR varbinary_starts_with(data, 0x4399af27)))
      OR (executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND tx_signer = '5qWya6UjwWnGVhdSBL3hyZ7B45jbk6Byt1hwd7ohEGXE' AND varbinary_starts_with(data, 0x8c55d7b0))
      OR (executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN' AND cardinality(account_arguments) >= 9 AND account_arguments[9] = '8rE9CtCjwhSmbwL5fbJBtRFsS3ohfMcDFeTTC7t4ciUA')
      OR (executing_account = 'waveQX2yP3H1pVU8djGvEHmYg8uamQ84AuyGtpsrXTF' AND cardinality(inner_instructions) > 0 AND inner_instructions[1].data = '11114XtYk9gGfZoo968fyjNUYQJKf9gdmkGoaoBpzFv4vyaSMBn3VKxZdv7mZLzoyX5YNC')
  ) s WHERE token_mint_address IS NOT NULL AND platform IS NOT NULL
  GROUP BY token_mint_address, platform
),
all_tokens AS (
  SELECT * FROM pumpdotfun_tokens_old UNION ALL
  SELECT * FROM pumpdotfun_tokens_new UNION ALL
  SELECT * FROM xfer_tokens UNION ALL
  SELECT * FROM call_tokens
)
SELECT DATE_TRUNC('day', time) AS day, platform, COUNT(*) AS daily_count
FROM all_tokens
WHERE DATE_TRUNC('day', time) >= CURRENT_DATE - INTERVAL '90' DAY
  AND DATE_TRUNC('day', time) < CURRENT_DATE
GROUP BY 1, 2
ORDER BY 1 DESC, 2
"""

# Graduation queries broken into groups to avoid Dune optimizer timeout.

# Group 1: Pumpdotfun + Boop
GRADS_GROUP1_SQL = """\
WITH pumpfun AS (
  SELECT DATE(block_time) AS block_date, 'Pumpdotfun' AS platform,
         COUNT(DISTINCT account_arguments[3]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE executing_account = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    AND bytearray_substring(data, 1, 8) = 0x9beae792ec9ea21e
    AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND (cardinality(inner_instructions) > 0 OR is_inner = true)
    AND tx_success = TRUE
  GROUP BY 1
),
boop AS (
  SELECT DATE(block_time) AS block_date, 'Boop' AS platform,
         COUNT(DISTINCT tx_id) AS daily_graduates
  FROM tokens_solana.transfers
  WHERE action = 'mint'
    AND outer_executing_account = 'boop8hVGQGqehUK2iVEMEnMrL5RbjywRzHKBmBE7ry4'
    AND inner_instruction_index = 17
    AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
  GROUP BY 1
)
SELECT * FROM pumpfun UNION ALL SELECT * FROM boop
ORDER BY block_date DESC, platform
"""

# Group 2: LetsBonk + LaunchLab (share launchlab_graduates_raw CTE)
GRADS_GROUP2_SQL = """\
WITH all_bonk_tokens AS (
  SELECT DISTINCT account_arguments[7] AS token_address
  FROM solana.instruction_calls
  WHERE block_time >= DATE '2025-04-26'
    AND executing_account = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj'
    AND (varbinary_starts_with(data, 0xafaf6d1f0d989bed) OR varbinary_starts_with(data, 0x4399af27))
    AND tx_success = TRUE
    AND (account_arguments[4] = 'FfYek5vEz23cMkWsdJwG2oa6EphsvXSHrGpdALN4g6W1' OR account_arguments[4] = 'BuM6KDpWiTcxvrpXywWFiw45R2RNH8WURdvqoTDV1BW4')
),
launchlab_graduates_old AS (
  SELECT block_time, tx_id,
    CASE
      WHEN inner_executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C' AND account_arguments[6] = 'So11111111111111111111111111111111111111112' THEN account_arguments[5]
      WHEN inner_executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C' THEN account_arguments[6]
      WHEN inner_executing_account = '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8' AND account_arguments[9] = 'So11111111111111111111111111111111111111112' THEN account_arguments[10]
      ELSE account_arguments[9]
    END AS token_address
  FROM solana.instruction_calls
  WHERE block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < DATE '2025-08-20'
    AND outer_executing_account = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj'
    AND ((inner_executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C' AND bytearray_substring(data, 1, 8) = 0xafaf6d1f0d989bed)
      OR (inner_executing_account = '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8' AND bytearray_substring(data, 1, 3) = 0x01fe00))
),
launchlab_graduates_new AS (
  SELECT block_time, tx_id,
    CASE WHEN account_arguments[7] = 'USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB' THEN account_arguments[6] ELSE account_arguments[7] END AS token_address
  FROM solana.instruction_calls
  WHERE block_time >= DATE '2025-08-19' AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND tx_signer = 'RAYpQbFNq9i3mu6cKpTKKRwwHFDeK5AuZz8xvxUrCgw'
    AND bytearray_substring(data, 1, 4) = 0x3f37fe41
    AND executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C'
    AND tx_success = true
),
launchlab_graduates_raw AS (
  SELECT block_time, tx_id, token_address FROM launchlab_graduates_old UNION ALL
  SELECT block_time, tx_id, token_address FROM launchlab_graduates_new
),
bonk AS (
  SELECT DATE(ll.block_time) AS block_date, 'LetsBonk' AS platform, COUNT(DISTINCT ll.tx_id) AS daily_graduates
  FROM launchlab_graduates_raw ll INNER JOIN all_bonk_tokens bonk ON ll.token_address = bonk.token_address
  GROUP BY 1
),
launchlab AS (
  SELECT DATE(block_time) AS block_date, 'LaunchLab' AS platform, COUNT(DISTINCT tx_id) AS daily_graduates
  FROM launchlab_graduates_raw WHERE token_address NOT IN (SELECT token_address FROM all_bonk_tokens)
  GROUP BY 1
)
SELECT * FROM bonk UNION ALL SELECT * FROM launchlab
ORDER BY block_date DESC, platform
"""

# Group 3: Believe + Bags + Sugar + Wavebreak
GRADS_GROUP3_SQL = """\
WITH all_believe_tokens AS (
  SELECT DISTINCT account_arguments[4] AS token_address
  FROM solana.instruction_calls
  WHERE executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND tx_signer = '5qWya6UjwWnGVhdSBL3hyZ7B45jbk6Byt1hwd7ohEGXE'
    AND bytearray_substring(data, 1, 4) = 0x8c55d7b0 AND tx_success = true
),
believe AS (
  SELECT DATE(block_time) AS block_date, 'Believe' AS platform, COUNT(DISTINCT account_arguments[14]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND bytearray_substring(data, 1, 4) = 0x9ca9e667 AND is_inner = true AND tx_success = true
    AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND CARDINALITY(account_arguments) >= 15
    AND account_arguments[14] IN (SELECT token_address FROM all_believe_tokens)
  GROUP BY 1
),
bags_launched AS (
  SELECT DISTINCT account_arguments[4] AS token_address
  FROM solana.instruction_calls
  WHERE executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND tx_signer = 'BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv'
    AND bytearray_substring(data, 1, 4) = 0x8c55d7b0 AND tx_success = true
),
bags AS (
  SELECT DATE(block_time) AS block_date, 'Bags' AS platform, COUNT(DISTINCT account_arguments[14]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE tx_signer IN ('CQdrEsYAxRqkwmpycuTwnMKggr3cr9fqY8Qma4J9TudY', 'DeQ8dPv6ReZNQ45NfiWwS5CchWpB2BVq1QMyNV8L2uSW')
    AND executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND bytearray_substring(data, 1, 8) = 0x9ca9e66735e45040 AND tx_success = true
    AND block_time >= DATE('2025-05-11') AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND account_arguments[14] IN (SELECT token_address FROM bags_launched)
  GROUP BY 1
),
sugar AS (
  SELECT DATE(block_time) AS block_date, 'Sugar' AS platform, COUNT(DISTINCT account_arguments[2]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE bytearray_substring(data, 1, 8) = 0x60e65b8c8b28eb8e
    AND executing_account = 'deus4Bvftd5QKcEkE5muQaWGWDoma8GrySvPFrBPjhS'
    AND tx_success = true AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
  GROUP BY 1
),
wavebreak AS (
  SELECT DATE(block_time) AS block_date, 'Wavebreak' AS platform, COUNT(DISTINCT account_arguments[9]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE executing_account = 'waveQX2yP3H1pVU8djGvEHmYg8uamQ84AuyGtpsrXTF'
    AND bytearray_substring(data, 1, 1) = 0x20 AND CARDINALITY(account_arguments) >= 9
    AND block_time >= DATE('2025-07-29') AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND tx_success = true
  GROUP BY 1
)
SELECT * FROM believe UNION ALL SELECT * FROM bags UNION ALL SELECT * FROM sugar UNION ALL SELECT * FROM wavebreak
ORDER BY block_date DESC, platform
"""

# Full multi-platform graduations — complex query, kept as reference.
# Too heavy for Dune SQL API optimizer (>240s). Use PUMPFUN_GRADUATIONS_SQL instead.
_LAUNCHPAD_GRADUATIONS_FULL_SQL = """\
WITH
all_bonk_tokens AS (
  SELECT DISTINCT account_arguments[7] AS token_address
  FROM solana.instruction_calls
  WHERE block_time >= DATE '2025-04-26'
    AND executing_account = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj'
    AND (varbinary_starts_with(data, 0xafaf6d1f0d989bed) OR varbinary_starts_with(data, 0x4399af27))
    AND tx_success = TRUE
    AND (account_arguments[4] = 'FfYek5vEz23cMkWsdJwG2oa6EphsvXSHrGpdALN4g6W1' OR account_arguments[4] = 'BuM6KDpWiTcxvrpXywWFiw45R2RNH8WURdvqoTDV1BW4')
),
launchlab_graduates_old AS (
  SELECT block_time, tx_id,
    CASE
      WHEN inner_executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C' AND account_arguments[6] = 'So11111111111111111111111111111111111111112' THEN account_arguments[5]
      WHEN inner_executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C' THEN account_arguments[6]
      WHEN inner_executing_account = '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8' AND account_arguments[9] = 'So11111111111111111111111111111111111111112' THEN account_arguments[10]
      ELSE account_arguments[9]
    END AS token_address
  FROM solana.instruction_calls
  WHERE block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < DATE '2025-08-20'
    AND outer_executing_account = 'LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj'
    AND ((inner_executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C' AND bytearray_substring(data, 1, 8) = 0xafaf6d1f0d989bed)
      OR (inner_executing_account = '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8' AND bytearray_substring(data, 1, 3) = 0x01fe00))
),
launchlab_graduates_new AS (
  SELECT block_time, tx_id,
    CASE WHEN account_arguments[7] = 'USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB' THEN account_arguments[6] ELSE account_arguments[7] END AS token_address
  FROM solana.instruction_calls
  WHERE block_time >= DATE '2025-08-19' AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND tx_signer = 'RAYpQbFNq9i3mu6cKpTKKRwwHFDeK5AuZz8xvxUrCgw'
    AND bytearray_substring(data, 1, 4) = 0x3f37fe41
    AND executing_account = 'CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C'
    AND tx_success = true
),
launchlab_graduates_raw AS (
  SELECT block_time, tx_id, token_address FROM launchlab_graduates_old UNION ALL
  SELECT block_time, tx_id, token_address FROM launchlab_graduates_new
),
bonk_graduates AS (
  SELECT DATE(ll.block_time) AS block_date, 'LetsBonk' AS platform, COUNT(DISTINCT ll.tx_id) AS daily_graduates
  FROM launchlab_graduates_raw ll INNER JOIN all_bonk_tokens bonk ON ll.token_address = bonk.token_address
  GROUP BY 1
),
launchlab_graduates AS (
  SELECT DATE(block_time) AS block_date, 'LaunchLab' AS platform, COUNT(DISTINCT tx_id) AS daily_graduates
  FROM launchlab_graduates_raw WHERE token_address NOT IN (SELECT token_address FROM all_bonk_tokens)
  GROUP BY 1
),
pumpfun_graduates AS (
  SELECT DATE(block_time) AS block_date, 'Pumpdotfun' AS platform, COUNT(DISTINCT account_arguments[3]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE executing_account = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    AND bytearray_substring(data, 1, 8) = 0x9beae792ec9ea21e
    AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND (cardinality(inner_instructions) > 0 OR is_inner = true)
    AND tx_success = TRUE
  GROUP BY 1
),
boop_graduates AS (
  SELECT DATE(block_time) AS block_date, 'Boop' AS platform, COUNT(DISTINCT tx_id) AS daily_graduates
  FROM tokens_solana.transfers
  WHERE action = 'mint' AND outer_executing_account = 'boop8hVGQGqehUK2iVEMEnMrL5RbjywRzHKBmBE7ry4'
    AND inner_instruction_index = 17
    AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
  GROUP BY 1
),
all_believe_tokens AS (
  SELECT DISTINCT account_arguments[4] AS token_address
  FROM solana.instruction_calls
  WHERE executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND tx_signer = '5qWya6UjwWnGVhdSBL3hyZ7B45jbk6Byt1hwd7ohEGXE'
    AND bytearray_substring(data, 1, 4) = 0x8c55d7b0 AND tx_success = true
),
believe_graduates AS (
  SELECT DATE(block_time) AS block_date, 'Believe' AS platform, COUNT(DISTINCT account_arguments[14]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND bytearray_substring(data, 1, 4) = 0x9ca9e667 AND is_inner = true AND tx_success = true
    AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND CARDINALITY(account_arguments) >= 15
    AND account_arguments[14] IN (SELECT token_address FROM all_believe_tokens)
  GROUP BY 1
),
wavebreak_graduates AS (
  SELECT DATE(block_time) AS block_date, 'Wavebreak' AS platform, COUNT(DISTINCT account_arguments[9]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE executing_account = 'waveQX2yP3H1pVU8djGvEHmYg8uamQ84AuyGtpsrXTF'
    AND bytearray_substring(data, 1, 1) = 0x20 AND CARDINALITY(account_arguments) >= 9
    AND block_time >= DATE('2025-07-29') AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND tx_success = true
  GROUP BY 1
),
bags_launched_tokens AS (
  SELECT DISTINCT account_arguments[4] AS token_address
  FROM solana.instruction_calls
  WHERE executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND tx_signer = 'BAGSB9TpGrZxQbEsrEznv5jXXdwyP6AXerN8aVRiAmcv'
    AND bytearray_substring(data, 1, 4) = 0x8c55d7b0 AND tx_success = true
),
bags_graduates AS (
  SELECT DATE(block_time) AS block_date, 'Bags' AS platform, COUNT(DISTINCT account_arguments[14]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE tx_signer IN ('CQdrEsYAxRqkwmpycuTwnMKggr3cr9fqY8Qma4J9TudY', 'DeQ8dPv6ReZNQ45NfiWwS5CchWpB2BVq1QMyNV8L2uSW')
    AND executing_account = 'dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN'
    AND bytearray_substring(data, 1, 8) = 0x9ca9e66735e45040 AND tx_success = true
    AND block_time >= DATE('2025-05-11') AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
    AND account_arguments[14] IN (SELECT token_address FROM bags_launched_tokens)
  GROUP BY 1
),
sugar_graduates AS (
  SELECT DATE(block_time) AS block_date, 'Sugar' AS platform, COUNT(DISTINCT account_arguments[2]) AS daily_graduates
  FROM solana.instruction_calls
  WHERE bytearray_substring(data, 1, 8) = 0x60e65b8c8b28eb8e
    AND executing_account = 'deus4Bvftd5QKcEkE5muQaWGWDoma8GrySvPFrBPjhS'
    AND tx_success = true AND block_time >= NOW() - INTERVAL '90' day AND DATE(block_time) < CURRENT_DATE
  GROUP BY 1
)
SELECT * FROM pumpfun_graduates UNION ALL
SELECT * FROM bonk_graduates UNION ALL
SELECT * FROM launchlab_graduates UNION ALL
SELECT * FROM boop_graduates UNION ALL
SELECT * FROM believe_graduates UNION ALL
SELECT * FROM wavebreak_graduates UNION ALL
SELECT * FROM bags_graduates UNION ALL
SELECT * FROM sugar_graduates
ORDER BY block_date DESC, platform
"""


async def _execute_sql_and_poll(
    http_client: httpx.AsyncClient,
    api_key: str,
    sql: str,
    timeout_seconds: int = 300,
    poll_interval: int = 15,
) -> list[dict] | None:
    """Execute inline SQL on Dune and poll for results."""
    headers = {"X-Dune-API-Key": api_key}

    resp = await http_client.post(
        f"{DUNE_API_BASE}/sql/execute",
        headers=headers,
        json={"sql": sql, "performance": "medium"},
        timeout=30.0,
    )
    if resp.status_code != 200:
        logger.error(f"Dune SQL execute failed: {resp.status_code} {resp.text[:200]}")
        return None

    execution_id = resp.json().get("execution_id")
    if not execution_id:
        logger.error("No execution_id from Dune SQL execute")
        return None

    logger.info(f"Dune SQL submitted, execution_id={execution_id}")

    elapsed = 0
    while elapsed < timeout_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        resp = await http_client.get(
            f"{DUNE_API_BASE}/execution/{execution_id}/results",
            headers=headers,
            timeout=30.0,
        )
        if resp.status_code != 200:
            logger.warning(f"Dune poll error: {resp.status_code}")
            continue

        result = resp.json()
        state = result.get("state")

        if state == "QUERY_STATE_COMPLETED":
            rows = result.get("result", {}).get("rows", [])
            logger.info(f"Dune SQL completed: {len(rows)} rows")
            return rows
        elif state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"):
            error = result.get("error", "unknown")
            logger.error(f"Dune SQL {state}: {error}")
            return None
        else:
            logger.debug(f"Dune SQL: {state} ({elapsed}s elapsed)")

    logger.error(f"Dune SQL timed out after {timeout_seconds}s")
    return None


async def _check_existing(engine, source: str) -> bool:
    async with get_session(engine) as session:
        result = await session.execute(
            select(func.count()).select_from(HistoricalData).where(HistoricalData.source == source)
        )
        return result.scalar() > 0


async def ingest_new_wallets(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily new wallet activation counts from Dune."""
    source = "new_wallets"
    if await _check_existing(engine, source):
        logger.info("New wallets data already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping new_wallets ingestion")
        return 0

    rows = await _execute_and_poll(http_client, api_key, QUERY_IDS["new_wallets"])
    if rows is None:
        logger.error("Failed to fetch new wallets data from Dune")
        return 0

    db_rows = []
    for row in rows:
        day_str = row.get("day")
        value = row.get("new_wallets")
        if day_str and value is not None:
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            db_rows.append(HistoricalData(source=source, date=dt, value=float(value)))

    async with get_session(engine) as session:
        session.add_all(db_rows)
        await session.commit()

    logger.info(f"Ingested {len(db_rows)} new_wallets data points from Dune")
    return len(db_rows)


async def ingest_priority_fees(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily median priority fee data from Dune."""
    source = "priority_fees"
    if await _check_existing(engine, source):
        logger.info("Priority fees data already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping priority_fees ingestion")
        return 0

    rows = await _execute_and_poll(http_client, api_key, QUERY_IDS["priority_fees"])
    if rows is None:
        logger.error("Failed to fetch priority fees data from Dune")
        return 0

    db_rows = []
    for row in rows:
        day_str = row.get("day")
        median_fee = row.get("median_priority_fee_sol")
        if day_str and median_fee is not None:
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            db_rows.append(HistoricalData(
                source=source,
                date=dt,
                value=float(median_fee),
                metadata_json=json.dumps({"median_sol": float(median_fee)}),
            ))

    async with get_session(engine) as session:
        session.add_all(db_rows)
        await session.commit()

    logger.info(f"Ingested {len(db_rows)} priority_fees data points from Dune")
    return len(db_rows)


async def ingest_launchpad_stats(engine, http_client: httpx.AsyncClient) -> int:
    """Fetch daily launch + graduation stats per launchpad from Dune.

    Uses adam_tehc's memecoin-wars queries covering all major launchpads:
    PumpFun, LetsBonk, Bags, Moonshot, Boop, Believe, LaunchLab, Wavebreak, etc.

    Stores per-platform creates as 'creates_{platform}' and total as 'pumpfun_creates'.
    Stores per-platform graduations as 'grads_{platform}' and total as 'pumpfun_graduations'.
    """
    if await _check_existing(engine, "pumpfun_creates"):
        logger.info("Launchpad stats already ingested, skipping")
        return 0

    api_key = _get_api_key()
    if not api_key:
        logger.info("DUNE_API_KEY not set, skipping launchpad stats")
        return 0

    total = 0

    # 1. Creates per platform
    rows = await _execute_sql_and_poll(http_client, api_key, LAUNCHPAD_CREATES_SQL, timeout_seconds=600)
    if rows:
        db_rows = []
        # Aggregate daily totals + per-platform
        daily_totals: dict[str, float] = {}
        for row in rows:
            day_str = row.get("day")
            platform = row.get("platform", "unknown")
            count = row.get("daily_count", 0)
            if not day_str:
                continue
            dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            dt_str = str(dt)
            daily_totals[dt_str] = daily_totals.get(dt_str, 0) + count
            db_rows.append(HistoricalData(
                source=f"creates_{platform.lower()}", date=dt, value=float(count)
            ))

        # Add daily totals as pumpfun_creates (for backward compat with launch monitor)
        for dt_str, total_count in daily_totals.items():
            dt = datetime.fromisoformat(dt_str).date()
            db_rows.append(HistoricalData(source="pumpfun_creates", date=dt, value=total_count))

        async with get_session(engine) as session:
            session.add_all(db_rows)
            await session.commit()
        total += len(db_rows)
        logger.info(f"Ingested {len(db_rows)} launchpad create rows from Dune")
    else:
        logger.error("Failed to fetch launchpad creates from Dune")

    # 2. Graduations — 3 group queries to avoid Dune optimizer timeout
    grad_rows = []
    for i, sql in enumerate([GRADS_GROUP1_SQL, GRADS_GROUP2_SQL, GRADS_GROUP3_SQL], 1):
        result = await _execute_sql_and_poll(http_client, api_key, sql, timeout_seconds=300)
        if result:
            grad_rows.extend(result)
            logger.info(f"Graduation group {i}: {len(result)} rows")
        else:
            logger.warning(f"Graduation group {i} failed")
    rows = grad_rows if grad_rows else None
    if rows:
        db_rows = []
        daily_totals = {}
        for row in rows:
            day_str = row.get("block_date")
            platform = row.get("platform", "unknown")
            count = row.get("daily_graduates", 0)
            if not day_str:
                continue
            dt = datetime.fromisoformat(str(day_str).replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
            dt_str = str(dt)
            daily_totals[dt_str] = daily_totals.get(dt_str, 0) + count
            db_rows.append(HistoricalData(
                source=f"grads_{platform.lower()}", date=dt, value=float(count)
            ))

        for dt_str, total_count in daily_totals.items():
            dt = datetime.fromisoformat(dt_str).date()
            db_rows.append(HistoricalData(source="pumpfun_graduations", date=dt, value=total_count))

        async with get_session(engine) as session:
            session.add_all(db_rows)
            await session.commit()
        total += len(db_rows)
        logger.info(f"Ingested {len(db_rows)} launchpad graduation rows from Dune")
    else:
        logger.error("Failed to fetch launchpad graduations from Dune")

    return total


async def refresh_launchpad_stats(engine, http_client: httpx.AsyncClient) -> int:
    """Hourly refresh: fetch latest launchpad stats and upsert recent days.

    Uses a simplified 3-day creates query + graduation query. Upserts all results.
    """
    api_key = _get_api_key()
    if not api_key:
        return 0

    updated = 0

    # Simplified creates query for last 3 days (all platforms)
    creates_sql = LAUNCHPAD_CREATES_SQL.replace("INTERVAL '120' DAY", "INTERVAL '3' DAY").replace("INTERVAL '90' DAY", "INTERVAL '3' DAY")

    rows = await _execute_sql_and_poll(http_client, api_key, creates_sql, timeout_seconds=300)
    if rows:
        daily_totals: dict[str, float] = {}
        async with get_session(engine) as session:
            for row in rows:
                day_str = row.get("day")
                platform = row.get("platform", "unknown")
                count = row.get("daily_count", 0)
                if not day_str:
                    continue
                dt = datetime.fromisoformat(day_str.replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
                dt_str = str(dt)
                daily_totals[dt_str] = daily_totals.get(dt_str, 0) + count

                source = f"creates_{platform.lower()}"
                existing = (await session.execute(
                    select(HistoricalData).where(HistoricalData.source == source).where(HistoricalData.date == dt)
                )).scalar_one_or_none()
                if existing:
                    existing.value = float(count)
                else:
                    session.add(HistoricalData(source=source, date=dt, value=float(count)))
                updated += 1

            # Upsert totals
            for dt_str, total_count in daily_totals.items():
                dt = datetime.fromisoformat(dt_str).date()
                existing = (await session.execute(
                    select(HistoricalData).where(HistoricalData.source == "pumpfun_creates").where(HistoricalData.date == dt)
                )).scalar_one_or_none()
                if existing:
                    existing.value = total_count
                else:
                    session.add(HistoricalData(source="pumpfun_creates", date=dt, value=total_count))

            await session.commit()

    if updated:
        logger.info(f"Refreshed {updated} launchpad create rows from Dune")
    return updated


async def refresh_launchpad_graduations(engine, http_client: httpx.AsyncClient) -> int:
    """Daily refresh of graduation data from all launchpad groups."""
    api_key = _get_api_key()
    if not api_key:
        return 0

    updated = 0
    for i, sql in enumerate([GRADS_GROUP1_SQL, GRADS_GROUP2_SQL, GRADS_GROUP3_SQL], 1):
        # Use 3-day window versions
        short_sql = sql.replace("INTERVAL '90' day", "INTERVAL '3' day")
        rows = await _execute_sql_and_poll(http_client, api_key, short_sql, timeout_seconds=300)
        if not rows:
            continue

        async with get_session(engine) as session:
            daily_totals: dict[str, float] = {}
            for row in rows:
                day_str = row.get("block_date")
                platform = row.get("platform", "unknown")
                count = row.get("daily_graduates", 0)
                if not day_str:
                    continue
                dt = datetime.fromisoformat(str(day_str).replace(" UTC", "+00:00").replace("Z", "+00:00")).date()
                dt_str = str(dt)
                daily_totals[dt_str] = daily_totals.get(dt_str, 0) + count

                source = f"grads_{platform.lower()}"
                existing = (await session.execute(
                    select(HistoricalData).where(HistoricalData.source == source).where(HistoricalData.date == dt)
                )).scalar_one_or_none()
                if existing:
                    existing.value = float(count)
                else:
                    session.add(HistoricalData(source=source, date=dt, value=float(count)))
                updated += 1

            # Upsert graduation totals
            for dt_str, total in daily_totals.items():
                dt = datetime.fromisoformat(dt_str).date()
                existing = (await session.execute(
                    select(HistoricalData).where(HistoricalData.source == "pumpfun_graduations").where(HistoricalData.date == dt)
                )).scalar_one_or_none()
                if existing:
                    existing.value = existing.value + total  # Add to existing (other groups may have run)
                else:
                    session.add(HistoricalData(source="pumpfun_graduations", date=dt, value=total))

            await session.commit()

    if updated:
        logger.info(f"Refreshed {updated} graduation rows from Dune")
    return updated
