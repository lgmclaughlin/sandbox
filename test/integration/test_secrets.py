"""Integration tests for secrets injection."""

from cli.lib.secrets import LocalProvider, get_secrets_for_container


class TestSecretsInjection:
    def test_full_lifecycle(self, tmp_path):
        """Test set, get, list, delete cycle."""
        provider = LocalProvider(path=tmp_path / "secrets.json")

        provider.set("API_KEY", "sk-abc123")
        provider.set("DB_PASS", "hunter2")
        provider.set("TOKEN", "tok-xyz")

        assert provider.list_keys() == ["API_KEY", "DB_PASS", "TOKEN"]
        assert provider.get("API_KEY") == "sk-abc123"
        assert provider.get("DB_PASS") == "hunter2"

        provider.delete("DB_PASS")
        assert provider.list_keys() == ["API_KEY", "TOKEN"]
        assert provider.get("DB_PASS") is None

    def test_secrets_for_container(self, tmp_path, monkeypatch):
        """Test that get_secrets_for_container collects all secrets."""
        provider = LocalProvider(path=tmp_path / "secrets.json")
        provider.set("KEY_1", "val_1")
        provider.set("KEY_2", "val_2")

        monkeypatch.setattr("cli.lib.secrets.get_provider", lambda _=None: provider)

        secrets = get_secrets_for_container()
        assert len(secrets) == 2
        assert secrets["KEY_1"] == "val_1"
        assert secrets["KEY_2"] == "val_2"

    def test_empty_secrets(self, tmp_path, monkeypatch):
        """Test that empty provider returns empty dict."""
        provider = LocalProvider(path=tmp_path / "secrets.json")
        monkeypatch.setattr("cli.lib.secrets.get_provider", lambda _=None: provider)

        secrets = get_secrets_for_container()
        assert secrets == {}

    def test_persistence_across_instances(self, tmp_path):
        """Test secrets persist between provider instances."""
        path = tmp_path / "secrets.json"

        p1 = LocalProvider(path=path)
        p1.set("PERSISTENT", "value")

        p2 = LocalProvider(path=path)
        assert p2.get("PERSISTENT") == "value"
        assert p2.list_keys() == ["PERSISTENT"]

    def test_update_existing(self, tmp_path):
        """Test that updating a secret replaces the value."""
        provider = LocalProvider(path=tmp_path / "secrets.json")
        provider.set("KEY", "old_value")
        provider.set("KEY", "new_value")

        assert provider.get("KEY") == "new_value"
        assert len(provider.list_keys()) == 1
