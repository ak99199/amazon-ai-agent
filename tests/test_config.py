from app.config import Settings
def test_missing_configuration(monkeypatch):
    for name in ("AMAZON_SP_API_CLIENT_ID","AMAZON_SP_API_CLIENT_SECRET","AMAZON_SP_REFRESH_TOKEN","AMAZON_SELLER_ID","AMAZON_MARKETPLACE_ID"): monkeypatch.delenv(name,raising=False)
    assert not Settings.from_environment().missing_fields == ()
def test_configuration(monkeypatch):
    for name in ("AMAZON_SP_API_CLIENT_ID","AMAZON_SP_API_CLIENT_SECRET","AMAZON_SP_REFRESH_TOKEN","AMAZON_SELLER_ID","AMAZON_MARKETPLACE_ID"): monkeypatch.setenv(name,"value")
    assert Settings.from_environment().require_complete().seller_id == "value"
