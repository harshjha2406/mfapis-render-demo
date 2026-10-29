"""Static safety checks for the public historical reference fallback."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_public_forex_fallback_uses_existing_historical_endpoints():
    js = (ROOT / "mfapis/static/forex.js").read_text()
    assert "'/v1/catalogue'" in js
    assert "'/v1/observations?'" in js
    assert "params.set('on',state.referenceDate)" in js
    assert "Historical ECB reference · not live" in js

def test_private_sifting_fetch_hidden_in_public_mode():
    js = (ROOT / "mfapis/static/forex.js").read_text()
    html = (ROOT / "mfapis/static/forex.html").read_text()
    assert "$('fetch-latest').hidden=true" in js
    assert 'id="mode-note"' in html
    assert "Live SiftingIO prices are available only in the private local demo" in js
    assert "api.sifting.io" not in js

def test_public_deployment_config_does_not_enable_live_redisplay():
    yaml = (ROOT / "render.yaml").read_text()
    assert 'FX_LIVE_DISPLAY_AUTHORIZED\n        value: "false"' in yaml
