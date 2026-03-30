"""Unit tests for proxy mode configuration."""

from cli.lib.docker import _is_proxy_mode, _generate_override, _compose_override_file


class TestProxyMode:
    def test_default_is_firewall_only(self, monkeypatch):
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {})
        assert _is_proxy_mode() is False

    def test_firewall_only_explicit(self, monkeypatch):
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_PROXY_MODE": "firewall-only",
        })
        assert _is_proxy_mode() is False

    def test_proxy_mode(self, monkeypatch):
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_PROXY_MODE": "proxy",
        })
        assert _is_proxy_mode() is True


class TestGenerateOverride:
    def _setup(self, tmp_path, monkeypatch):
        (tmp_path / "docker").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("cli.lib.docker.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("cli.lib.config.list_available_tools", lambda: [])

    def test_no_overrides(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {})

        _generate_override()
        assert not _compose_override_file().exists()

    def test_cpu_limit(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_CPU_LIMIT": "2.0",
        })

        _generate_override()
        content = _compose_override_file().read_text()
        assert "cpus" in content
        assert "2.0" in content

    def test_mem_limit(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_MEM_LIMIT": "4g",
        })

        _generate_override()
        content = _compose_override_file().read_text()
        assert "memory" in content

    def test_hardened_mode(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_HARDENED_MODE": "true",
        })

        _generate_override()
        content = _compose_override_file().read_text()
        assert "read_only" in content
        assert "cap_drop" in content
        assert "tmpfs" in content

    def test_proxy_mode_override(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_PROXY_MODE": "proxy",
        })

        _generate_override()
        content = _compose_override_file().read_text()
        assert "HTTP_PROXY" in content
        assert "HTTPS_PROXY" in content
        assert "proxy_certs" in content

    def test_cleanup_when_no_overrides(self, tmp_path, monkeypatch):
        self._setup(tmp_path, monkeypatch)
        override = _compose_override_file()
        override.write_text("old content")
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {})

        _generate_override()
        assert not override.exists()
