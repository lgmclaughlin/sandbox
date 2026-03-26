"""Unit tests for firewall lib functions."""

from cli.lib.firewall import (
    WHITELIST_FILE,
    add_domain,
    read_whitelist,
    remove_domain,
    validate_domain,
    write_whitelist,
    merge_tool_domains,
)


class TestValidateDomain:
    def test_valid_domains(self):
        assert validate_domain("example.com")
        assert validate_domain("api.example.com")
        assert validate_domain("sub.deep.example.co.uk")
        assert validate_domain("registry.npmjs.org")

    def test_invalid_domains(self):
        assert not validate_domain("")
        assert not validate_domain("not a domain!")
        assert not validate_domain("http://example.com")
        assert not validate_domain("example")
        assert not validate_domain(".example.com")
        assert not validate_domain("example.")
        assert not validate_domain("exam ple.com")

    def test_hyphens_allowed(self):
        assert validate_domain("my-api.example.com")
        assert validate_domain("a-b-c.test.io")

    def test_hyphen_edges(self):
        assert not validate_domain("-example.com")


class TestReadWriteWhitelist:
    def test_read_existing(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("example.com\ntest.org\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        assert read_whitelist() == ["example.com", "test.org"]

    def test_read_missing(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        assert read_whitelist() == []

    def test_read_skips_comments_and_blanks(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("# comment\nexample.com\n\n# another\ntest.org\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        assert read_whitelist() == ["example.com", "test.org"]

    def test_write_roundtrip(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        domains = ["example.com", "test.org"]
        write_whitelist(domains)
        assert read_whitelist() == domains


class TestAddRemoveDomain:
    def test_add_new(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("existing.com\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        assert add_domain("new.com") is True
        assert "new.com" in read_whitelist()

    def test_add_duplicate(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("existing.com\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        assert add_domain("existing.com") is False

    def test_remove_existing(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("a.com\nb.com\nc.com\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        assert remove_domain("b.com") is True
        assert read_whitelist() == ["a.com", "c.com"]

    def test_remove_missing(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("a.com\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        assert remove_domain("nope.com") is False


class TestMergeToolDomains:
    def test_merge_adds_new(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("existing.com\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        merge_tool_domains(["new1.com", "new2.com"])
        domains = read_whitelist()
        assert "existing.com" in domains
        assert "new1.com" in domains
        assert "new2.com" in domains

    def test_merge_no_duplicates(self, tmp_path, monkeypatch):
        wl = tmp_path / "whitelist.txt"
        wl.write_text("existing.com\n")
        monkeypatch.setattr("cli.lib.firewall.WHITELIST_FILE", wl)

        merge_tool_domains(["existing.com", "new.com"])
        domains = read_whitelist()
        assert domains.count("existing.com") == 1
