"""Unit tests for firewall profiles."""

from cli.lib.firewall import (
    list_profiles,
    load_profile,
    read_whitelist,
    write_whitelist,
)


class TestListProfiles:
    def test_lists_profiles(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "dev.yaml").write_text(
            "name: dev\ndescription: Dev\ndomains:\n  - example.com\n"
        )
        (profiles_dir / "prod.yaml").write_text(
            "name: prod\ndescription: Prod\ndomains: []\n"
        )
        monkeypatch.setattr("cli.lib.firewall.PROFILES_DIR", profiles_dir)

        profiles = list_profiles()
        assert len(profiles) == 2
        names = [p["name"] for p in profiles]
        assert "dev" in names
        assert "prod" in names

    def test_empty_dir(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        monkeypatch.setattr("cli.lib.firewall.PROFILES_DIR", profiles_dir)

        assert list_profiles() == []

    def test_missing_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.firewall.PROFILES_DIR", tmp_path / "nope")
        assert list_profiles() == []


class TestLoadProfile:
    def test_load_existing(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "dev.yaml").write_text(
            "name: dev\ndomains:\n  - a.com\n  - b.com\n"
        )
        monkeypatch.setattr("cli.lib.firewall.PROFILES_DIR", profiles_dir)

        profile = load_profile("dev")
        assert profile is not None
        assert profile["domains"] == ["a.com", "b.com"]

    def test_load_missing(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        monkeypatch.setattr("cli.lib.firewall.PROFILES_DIR", profiles_dir)

        assert load_profile("nonexistent") is None


class TestApplyProfile:
    def test_replaces_whitelist_with_profile_and_tool_domains(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "dev.yaml").write_text(
            "name: dev\ndomains:\n  - profile.com\n"
        )
        monkeypatch.setattr("cli.lib.firewall.PROFILES_DIR", profiles_dir)

        wl = tmp_path / "whitelist.txt"
        wl.write_text("old-domain.com\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "tool.yaml").write_text(
            "name: tool\nfirewall:\n  domains:\n    - tool.com\n"
        )
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tools_dir)

        from cli.lib.firewall import apply_profile
        ok, msg = apply_profile("dev")
        assert ok

        domains = read_whitelist()
        assert "profile.com" in domains
        assert "tool.com" in domains
        assert "old-domain.com" not in domains

    def test_missing_profile(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        monkeypatch.setattr("cli.lib.firewall.PROFILES_DIR", profiles_dir)

        from cli.lib.firewall import apply_profile
        ok, msg = apply_profile("nonexistent")
        assert not ok
        assert "not found" in msg
