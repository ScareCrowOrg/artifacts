"""
Unit tests for artifacts/shared/config_manager.py.

Validates:
- get_config() with "vault." prefix routes to SecretClient.
- get_config() with regular key reads from Redis settings:{key}.
- In-memory cache (60 s TTL) is populated and returned on second call.
- Cache is bypassed for vault.* keys (secrets never cached).
- Fallback to os.getenv when Redis is unavailable.
- Fallback to os.getenv when SecretClient is unavailable.
- Returns None when key is absent from all sources.
- clear_cache() flushes the in-memory store.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# sys.path setup: make artifacts/shared importable as a package
# ---------------------------------------------------------------------------

_shared_dir = Path(__file__).resolve().parents[2]  # artifacts/
if str(_shared_dir) not in sys.path:
    sys.path.insert(0, str(_shared_dir))

# Import after path setup
from shared.config_manager import clear_cache, get_config  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_mock(key_values: dict):
    """Return a mock Redis client that serves key_values from .get()."""
    mock = MagicMock()
    mock.get.side_effect = lambda k: key_values.get(k)
    return mock


# ---------------------------------------------------------------------------
# Fixture: reset cache between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# Tests: vault.* prefix → SecretClient
# ---------------------------------------------------------------------------


class TestVaultKeyResolution:
    def test_vault_key_routes_to_secret_client(self):
        """vault.* key requests the secret from SecretClient."""
        mock_client = MagicMock()
        mock_client.request_secret.return_value = "super-secret"

        with patch("shared.config_manager._get_secret_client", return_value=mock_client):
            result = get_config("vault.redis_password")

        assert result == "super-secret"
        mock_client.request_secret.assert_called_once_with("redis_password")

    def test_vault_key_strips_prefix_before_requesting(self):
        """The 'vault.' prefix is stripped when calling SecretClient."""
        mock_client = MagicMock()
        mock_client.request_secret.return_value = "mongodb-uri-value"

        with patch("shared.config_manager._get_secret_client", return_value=mock_client):
            get_config("vault.mongodb_uri")

        mock_client.request_secret.assert_called_once_with("mongodb_uri")

    def test_vault_key_not_cached(self):
        """Secrets are never stored in the in-memory cache."""
        mock_client = MagicMock()
        mock_client.request_secret.return_value = "fresh-secret"

        with patch("shared.config_manager._get_secret_client", return_value=mock_client):
            get_config("vault.api_key")
            get_config("vault.api_key")  # second call

        # SecretClient must be invoked both times (no caching for secrets)
        assert mock_client.request_secret.call_count == 2

    def test_vault_key_falls_back_to_env_when_secret_client_unavailable(self, monkeypatch):
        """When SecretClient is None, vault.* resolves via os.getenv."""
        monkeypatch.setenv("REDIS_PASSWORD", "env-redis-pw")

        with patch("shared.config_manager._get_secret_client", return_value=None):
            result = get_config("vault.redis_password")

        assert result == "env-redis-pw"

    def test_vault_key_falls_back_to_env_when_client_returns_none(self, monkeypatch):
        """SecretClient returning None falls back to os.getenv."""
        monkeypatch.setenv("MONGODB_URI", "mongodb://fallback")
        mock_client = MagicMock()
        mock_client.request_secret.return_value = None

        with patch("shared.config_manager._get_secret_client", return_value=mock_client):
            result = get_config("vault.mongodb_uri")

        assert result == "mongodb://fallback"

    def test_vault_key_returns_none_when_not_found_anywhere(self):
        """Returns None when SecretClient returns None and env var absent."""
        mock_client = MagicMock()
        mock_client.request_secret.return_value = None

        with patch("shared.config_manager._get_secret_client", return_value=mock_client):
            result = get_config("vault.nonexistent_secret")

        assert result is None

    def test_vault_key_falls_back_to_env_on_secret_client_exception(self, monkeypatch):
        """SecretClient exception triggers fallback to os.getenv."""
        monkeypatch.setenv("API_SECRET", "env-fallback-secret")
        mock_client = MagicMock()
        mock_client.request_secret.side_effect = ConnectionError("Redis down")

        with patch("shared.config_manager._get_secret_client", return_value=mock_client):
            result = get_config("vault.api_secret")

        assert result == "env-fallback-secret"


# ---------------------------------------------------------------------------
# Tests: regular key → Redis settings + env fallback
# ---------------------------------------------------------------------------


class TestSettingsKeyResolution:
    def test_settings_key_reads_from_redis(self):
        """Regular key resolves from Redis settings:{key}."""
        mock_redis = _make_redis_mock({"settings:api_host": "0.0.0.0"})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("api_host")

        assert result == "0.0.0.0"

    def test_settings_key_decodes_json_string(self):
        """JSON-encoded string values are decoded to plain strings."""
        mock_redis = _make_redis_mock({"settings:api_port": '"5050"'})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("api_port")

        assert result == "5050"

    def test_settings_key_converts_json_number_to_string(self):
        """JSON-encoded numeric values are converted to str."""
        mock_redis = _make_redis_mock({"settings:api_port": "5050"})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("api_port")

        assert result == "5050"

    def test_settings_key_falls_back_to_env_when_redis_missing_key(self, monkeypatch):
        """Falls back to os.getenv when Redis key is absent."""
        monkeypatch.setenv("DB_URL", "sqlite:///fallback.db")
        mock_redis = _make_redis_mock({})  # empty Redis

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("db_url")

        assert result == "sqlite:///fallback.db"

    def test_settings_key_falls_back_to_env_when_redis_unavailable(self, monkeypatch):
        """Falls back to os.getenv when Redis client is None."""
        monkeypatch.setenv("API_HOST", "127.0.0.1")

        with patch("shared.config_manager._get_redis_client", return_value=None):
            result = get_config("api_host")

        assert result == "127.0.0.1"

    def test_settings_key_returns_none_when_not_found_anywhere(self):
        """Returns None when key absent from Redis and env."""
        mock_redis = _make_redis_mock({})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("totally_nonexistent_key_xyz")

        assert result is None

    def test_settings_key_env_fallback_uppercases_key(self, monkeypatch):
        """Env lookup uses UPPER_SNAKE_CASE version of the config key."""
        monkeypatch.setenv("REDIS_HOST", "redis-env-host")
        mock_redis = _make_redis_mock({})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("redis_host")

        assert result == "redis-env-host"

    def test_settings_key_env_colon_separator_converted(self, monkeypatch):
        """Colon-separated keys are converted to underscores for env lookup."""
        monkeypatch.setenv("REDIS_HOST", "colon-host")
        mock_redis = _make_redis_mock({})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("redis:host")

        assert result == "colon-host"

    def test_redis_exception_falls_back_to_env(self, monkeypatch):
        """Redis exception during GET triggers fallback to env."""
        monkeypatch.setenv("API_HOST", "env-host-fallback")
        mock_redis = MagicMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            result = get_config("api_host")

        assert result == "env-host-fallback"


# ---------------------------------------------------------------------------
# Tests: In-memory cache
# ---------------------------------------------------------------------------


class TestInMemoryCache:
    def test_cache_is_populated_on_first_call(self):
        """Value from Redis is cached on first successful lookup."""
        mock_redis = _make_redis_mock({"settings:api_host": "cached-host"})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            get_config("api_host")
            get_config("api_host")  # second call

        # Redis should only be queried once; second call uses cache
        assert mock_redis.get.call_count == 1

    def test_cache_returns_same_value_on_second_call(self):
        """Cached value is returned without hitting Redis again."""
        mock_redis = _make_redis_mock({"settings:api_host": "cached-host"})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            first = get_config("api_host")
            second = get_config("api_host")

        assert first == second == "cached-host"

    def test_clear_cache_flushes_all_entries(self):
        """clear_cache() forces a fresh Redis lookup on next call."""
        mock_redis = _make_redis_mock({"settings:api_host": "original"})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            get_config("api_host")
            clear_cache()
            get_config("api_host")

        # Redis queried twice: once before clear, once after
        assert mock_redis.get.call_count == 2

    def test_cache_expires_after_ttl(self):
        """Cached entry is evicted after 60 seconds and re-fetched from Redis."""
        import shared.config_manager as cm

        mock_redis = _make_redis_mock({"settings:ttl_key": "value-a"})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            get_config("ttl_key")
            # Manually expire the cache entry
            cm._cache["ttl_key"] = ("value-a", time.monotonic() - 1)
            get_config("ttl_key")

        # Should have re-queried Redis after expiry
        assert mock_redis.get.call_count == 2

    def test_env_fallback_value_is_also_cached(self, monkeypatch):
        """Env-var fallback values are stored in the cache too."""
        monkeypatch.setenv("MY_SETTING", "from-env")
        mock_redis = _make_redis_mock({})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            get_config("my_setting")
            get_config("my_setting")  # second call should use cache

        assert mock_redis.get.call_count == 1


# ---------------------------------------------------------------------------
# Tests: clear_cache
# ---------------------------------------------------------------------------


class TestClearCache:
    def test_clear_cache_empties_internal_dict(self):
        """clear_cache() empties the _cache dictionary."""
        import shared.config_manager as cm

        mock_redis = _make_redis_mock({"settings:k1": "v1", "settings:k2": "v2"})

        with patch("shared.config_manager._get_redis_client", return_value=mock_redis):
            get_config("k1")
            get_config("k2")

        assert len(cm._cache) == 2
        clear_cache()
        assert len(cm._cache) == 0
