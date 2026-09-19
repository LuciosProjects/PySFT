from pysft.core.tase_specific_utils import get_tase_datahub_api_headers


def test_tase_api_key_is_read_when_headers_are_built(monkeypatch):
    monkeypatch.setenv("TASE_DATAHUB_API_KEY", "first-key")
    assert get_tase_datahub_api_headers()["apikey"] == "first-key"

    monkeypatch.setenv("TASE_DATAHUB_API_KEY", "rotated-key")
    assert get_tase_datahub_api_headers()["apikey"] == "rotated-key"


def test_explicit_tase_api_key_overrides_environment(monkeypatch):
    monkeypatch.setenv("TASE_DATAHUB_API_KEY", "environment-key")
    assert get_tase_datahub_api_headers("explicit-key")["apikey"] == "explicit-key"


def test_missing_tase_api_key_is_not_persisted(monkeypatch):
    monkeypatch.delenv("TASE_DATAHUB_API_KEY", raising=False)
    assert get_tase_datahub_api_headers()["apikey"] == ""
