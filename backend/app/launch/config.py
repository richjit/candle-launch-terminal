"""Launchpad identification configuration.

Maps DEX names, dexIds, and address patterns to canonical launchpad names.
Add new launchpads by extending the dicts below.
"""

# Canonical launchpad name → program address (for RPC counting)
LAUNCHPAD_PROGRAMS: dict[str, str] = {
    "pumpfun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    # "candle": "TBD",  # Candle TV v2 — uncomment when launched
}

# GeckoTerminal DEX name (case-insensitive) → launchpad
DEX_NAME_MAP: dict[str, str] = {
    "pumpswap": "pumpfun",
    "pump.fun": "pumpfun",
    "bonk launcher": "bonk",
    "bonk": "bonk",
    "bags": "bags",
    "candle": "candle",
}

# DexScreener dexId → launchpad
DEX_ID_MAP: dict[str, str] = {
    "pumpswap": "pumpfun",
}

# Token address suffix → launchpad
ADDRESS_SUFFIX_MAP: dict[str, str] = {
    "pump": "pumpfun",
}

SUPPORTED_LAUNCHPADS = {"pumpfun", "bonk", "bags", "candle"}


def identify_launchpad(
    dex_name: str | None = None,
    token_address: str | None = None,
    dex_id: str | None = None,
) -> str | None:
    """Identify which launchpad a token came from using multiple signals.

    Returns canonical launchpad name or None if not from a known launchpad.
    """
    # Check DEX name (from GeckoTerminal)
    if dex_name:
        key = dex_name.lower().strip()
        if key in DEX_NAME_MAP:
            return DEX_NAME_MAP[key]

    # Check dexId (from DexScreener)
    if dex_id:
        key = dex_id.lower().strip()
        if key in DEX_ID_MAP:
            return DEX_ID_MAP[key]

    # Check address suffix
    if token_address:
        for suffix, launchpad in ADDRESS_SUFFIX_MAP.items():
            if token_address.lower().endswith(suffix):
                return launchpad

    return None
