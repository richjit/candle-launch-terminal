from app.launch.config import identify_launchpad


def test_identify_pumpfun_by_dex_name():
    assert identify_launchpad(dex_name="PumpSwap", token_address="abc123pump", dex_id=None) == "pumpfun"


def test_identify_pumpfun_by_address_suffix():
    assert identify_launchpad(dex_name="Raydium", token_address="So1abc123pump", dex_id=None) == "pumpfun"


def test_identify_pumpfun_by_dex_id():
    assert identify_launchpad(dex_name=None, token_address="abc", dex_id="pumpswap") == "pumpfun"


def test_identify_unknown_returns_none():
    assert identify_launchpad(dex_name="Raydium", token_address="abc123xyz", dex_id="raydium") is None


def test_identify_bonk():
    assert identify_launchpad(dex_name="Bonk Launcher", token_address="abc", dex_id=None) == "bonk"


def test_supported_launchpads_list():
    from app.launch.config import SUPPORTED_LAUNCHPADS
    assert "pumpfun" in SUPPORTED_LAUNCHPADS
    assert "bonk" in SUPPORTED_LAUNCHPADS
    assert "bags" in SUPPORTED_LAUNCHPADS
