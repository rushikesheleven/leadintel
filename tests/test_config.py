"""Tests for configuration loading."""

from leadintel.config import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.log_level == "INFO"
        assert s.demo_mode is False  # Default is now False (live mode)
        assert s.overpass_radius_m == 5000
        assert s.cache_ttl == 3600
        assert s.respect_robots is True
        assert s.ollama_enabled is False

    def test_overpass_defaults(self):
        s = Settings()
        assert "overpass-api.de" in s.overpass_endpoint
        assert s.overpass_radius_m == 5000

    def test_ollama_defaults(self):
        s = Settings()
        assert s.ollama_enabled is False
        assert s.ollama_base_url == "http://localhost:11434"
        assert s.ollama_model == "llama3"
        assert s.has_ollama is False

    def test_has_google_places_false_when_key_empty(self):
        s = Settings()
        assert s.has_google_places is False

    def test_has_gemini_false_when_key_empty(self):
        s = Settings()
        assert s.has_gemini is False

    def test_safe_dict_redacts_keys(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "secret_key_abc")
        monkeypatch.setenv("GEMINI_API_KEY", "another_secret")
        s = Settings()
        d = s.safe_dict()
        assert d["google_places_api_key"] == "***"
        assert d["gemini_api_key"] == "***"
        for v in d.values():
            assert "secret_key_abc" not in str(v)
            assert "another_secret" not in str(v)

    def test_safe_dict_not_set_label(self):
        s = Settings()
        d = s.safe_dict()
        assert d["google_places_api_key"] == "(not set)"

    def test_safe_dict_exposes_non_secret_settings(self):
        s = Settings()
        d = s.safe_dict()
        assert "overpass_endpoint" in d
        assert "demo_mode" in d
        assert "ollama_enabled" in d

    def test_demo_mode_env(self, monkeypatch):
        monkeypatch.setenv("DEMO_MODE", "true")
        s = Settings()
        assert s.demo_mode is True

    def test_ollama_enabled_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_ENABLED", "true")
        monkeypatch.setenv("OLLAMA_MODEL", "mistral")
        s = Settings()
        assert s.ollama_enabled is True
        assert s.ollama_model == "mistral"
        assert s.has_ollama is True

    def test_overpass_radius_env(self, monkeypatch):
        monkeypatch.setenv("OVERPASS_RADIUS_M", "10000")
        s = Settings()
        assert s.overpass_radius_m == 10000
