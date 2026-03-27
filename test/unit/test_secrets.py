"""Unit tests for secrets provider interface."""

from cli.lib.secrets import (
    EnvProvider,
    LocalProvider,
    get_provider,
    get_secrets_for_container,
    mask_value,
)


class TestLocalProvider:
    def test_set_and_get(self, tmp_path):
        provider = LocalProvider(path=tmp_path / "secrets.json")
        provider.set("MY_KEY", "my_value")
        assert provider.get("MY_KEY") == "my_value"

    def test_get_missing(self, tmp_path):
        provider = LocalProvider(path=tmp_path / "secrets.json")
        assert provider.get("NONEXISTENT") is None

    def test_list_keys(self, tmp_path):
        provider = LocalProvider(path=tmp_path / "secrets.json")
        provider.set("KEY_A", "val_a")
        provider.set("KEY_B", "val_b")
        assert provider.list_keys() == ["KEY_A", "KEY_B"]

    def test_delete(self, tmp_path):
        provider = LocalProvider(path=tmp_path / "secrets.json")
        provider.set("KEY", "val")
        assert provider.delete("KEY") is True
        assert provider.get("KEY") is None

    def test_delete_missing(self, tmp_path):
        provider = LocalProvider(path=tmp_path / "secrets.json")
        assert provider.delete("NOPE") is False

    def test_roundtrip_special_chars(self, tmp_path):
        provider = LocalProvider(path=tmp_path / "secrets.json")
        value = "sk-abc123!@#$%^&*()_+-=[]{}|;':\",./<>?"
        provider.set("SPECIAL", value)
        assert provider.get("SPECIAL") == value

    def test_persistence(self, tmp_path):
        path = tmp_path / "secrets.json"
        provider1 = LocalProvider(path=path)
        provider1.set("PERSIST", "value")

        provider2 = LocalProvider(path=path)
        assert provider2.get("PERSIST") == "value"

    def test_file_permissions(self, tmp_path):
        import stat
        path = tmp_path / "secrets.json"
        provider = LocalProvider(path=path)
        provider.set("KEY", "val")
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600

    def test_overwrite(self, tmp_path):
        provider = LocalProvider(path=tmp_path / "secrets.json")
        provider.set("KEY", "old")
        provider.set("KEY", "new")
        assert provider.get("KEY") == "new"
        assert provider.list_keys() == ["KEY"]


class TestEnvProvider:
    def test_get_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_SECRET", "from_env")
        provider = EnvProvider()
        assert provider.get("TEST_SECRET") == "from_env"

    def test_get_missing(self):
        provider = EnvProvider()
        assert provider.get("SURELY_NOT_SET_12345") is None

    def test_set_raises(self):
        provider = EnvProvider()
        try:
            provider.set("KEY", "val")
            assert False, "Should have raised"
        except RuntimeError:
            pass

    def test_delete_raises(self):
        provider = EnvProvider()
        try:
            provider.delete("KEY")
            assert False, "Should have raised"
        except RuntimeError:
            pass

    def test_list_empty(self):
        provider = EnvProvider()
        assert provider.list_keys() == []


class TestGetProvider:
    def test_local(self):
        provider = get_provider("local")
        assert isinstance(provider, LocalProvider)

    def test_env(self):
        provider = get_provider("env")
        assert isinstance(provider, EnvProvider)

    def test_unknown(self):
        try:
            get_provider("vault")
            assert False, "Should have raised"
        except ValueError:
            pass


class TestMaskValue:
    def test_short(self):
        assert mask_value("abc") == "****"

    def test_normal(self):
        masked = mask_value("sk-1234567890")
        assert masked.startswith("sk")
        assert masked.endswith("90")
        assert "****" in masked or "*" in masked

    def test_exact_four(self):
        assert mask_value("abcd") == "****"


class TestGetSecretsForContainer:
    def test_collects_secrets(self, tmp_path, monkeypatch):
        path = tmp_path / "secrets.json"
        provider = LocalProvider(path=path)
        provider.set("API_KEY", "sk-123")
        provider.set("DB_PASS", "secret")

        monkeypatch.setattr("cli.lib.secrets.get_provider", lambda _=None: provider)
        secrets = get_secrets_for_container()
        assert secrets["API_KEY"] == "sk-123"
        assert secrets["DB_PASS"] == "secret"
