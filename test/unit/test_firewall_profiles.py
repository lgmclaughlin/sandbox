"""Unit tests for firewall profiles."""

import pytest

from cli.lib.firewall import (
    list_profiles,
    load_profile,
    read_whitelist,
)


@pytest.fixture
def fw_profile_setup(tmp_path, monkeypatch):
    """Set up firewall profile test environment."""
    (tmp_path / "config" / "firewall" / "profiles").mkdir(parents=True)
    (tmp_path / "docker" / "firewall").mkdir(parents=True)
    monkeypatch.setattr("cli.lib.firewall.get_data_dir", lambda: tmp_path)
    return tmp_path


class TestListProfiles:
    def test_lists_profiles(self, fw_profile_setup):
        profiles_dir = fw_profile_setup / "config" / "firewall" / "profiles"
        (profiles_dir / "dev.yaml").write_text(
            "name: dev\ndescription: Dev\ndomains:\n  - example.com\n"
        )
        (profiles_dir / "prod.yaml").write_text(
            "name: prod\ndescription: Prod\ndomains: []\n"
        )

        profiles = list_profiles()
        assert len(profiles) == 2
        names = [p["name"] for p in profiles]
        assert "dev" in names
        assert "prod" in names

    def test_empty_dir(self, fw_profile_setup):
        assert list_profiles() == []

    def test_missing_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.firewall.get_data_dir", lambda: tmp_path / "nope")
        assert list_profiles() == []


class TestLoadProfile:
    def test_load_existing(self, fw_profile_setup):
        profiles_dir = fw_profile_setup / "config" / "firewall" / "profiles"
        (profiles_dir / "dev.yaml").write_text(
            "name: dev\ndomains:\n  - a.com\n  - b.com\n"
        )

        profile = load_profile("dev")
        assert profile is not None
        assert profile["domains"] == ["a.com", "b.com"]

    def test_load_missing(self, fw_profile_setup):
        assert load_profile("nonexistent") is None


class TestApplyProfile:
    def test_replaces_whitelist_with_profile_and_tool_domains(self, fw_profile_setup, monkeypatch):
        profiles_dir = fw_profile_setup / "config" / "firewall" / "profiles"
        (profiles_dir / "dev.yaml").write_text(
            "name: dev\ndomains:\n  - profile.com\n"
        )

        wl = fw_profile_setup / "docker" / "firewall" / "whitelist.txt"
        wl.write_text("old-domain.com\n")

        tools_dir = fw_profile_setup / "config" / "tools"
        tools_dir.mkdir(parents=True)
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

    def test_missing_profile(self, fw_profile_setup):
        from cli.lib.firewall import apply_profile
        ok, msg = apply_profile("nonexistent")
        assert not ok
        assert "not found" in msg
