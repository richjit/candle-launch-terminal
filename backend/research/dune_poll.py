"""Poll Dune executions and save results to DB when they complete."""
import json
import os
import sys
import time
import sqlite3
from datetime import datetime

import httpx

API_KEY = os.environ.get("DUNE_API_KEY", "")
BASE = "https://api.dune.com/api/v1"
DB_PATH = "candle.db"

EXECUTIONS = {
    "new_wallets": "01KMR5E23NWMG05Q5ZT6YB7GEN",
    "priority_fees": "01KMR5M0MBSEJ5K6KV46Y9S5MH",
}


def check_and_ingest(source: str, execution_id: str):
    headers = {"X-Dune-API-Key": API_KEY}
    client = httpx.Client()

    print(f"[{source}] Checking execution {execution_id}...")
    resp = client.get(f"{BASE}/execution/{execution_id}/results", headers=headers, timeout=30)
    data = resp.json()

    state = data.get("state")
    print(f"[{source}] State: {state}")

    if state != "QUERY_STATE_COMPLETED":
        credits = data.get("execution_cost_credits", "?")
        print(f"[{source}] Still running, credits used: {credits}")
        return False

    rows = data.get("result", {}).get("rows", [])
    print(f"[{source}] Completed! {len(rows)} rows")

    if not rows:
        return True

    # Check if already ingested
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM historical_data WHERE source = ?", (source,))
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"[{source}] Already have {existing} rows, skipping")
        conn.close()
        return True

    # Insert
    for row in rows:
        day_str = row.get("day")
        if source == "new_wallets":
            value = row.get("new_wallets")
            meta = None
        else:
            value = row.get("median_priority_fee_sol")
            meta = json.dumps({"median_sol": value})

        if day_str and value is not None:
            dt = day_str[:10]  # YYYY-MM-DD
            cur.execute(
                "INSERT OR IGNORE INTO historical_data (source, date, value, metadata_json) VALUES (?, ?, ?, ?)",
                (source, dt, float(value), meta),
            )

    conn.commit()
    inserted = conn.total_changes
    print(f"[{source}] Inserted {inserted} rows")
    conn.close()
    return True


def main():
    if not API_KEY:
        print("Set DUNE_API_KEY env var")
        sys.exit(1)

    remaining = dict(EXECUTIONS)
    while remaining:
        for source, eid in list(remaining.items()):
            done = check_and_ingest(source, eid)
            if done:
                del remaining[source]

        if remaining:
            print(f"\nWaiting 30s... ({len(remaining)} queries still running)")
            time.sleep(30)

    print("\nAll done!")


if __name__ == "__main__":
    main()
