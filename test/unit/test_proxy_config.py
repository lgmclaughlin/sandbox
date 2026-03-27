"""Unit tests for proxy mode configuration."""

from cli.lib.docker import _is_proxy_mode, _generate_override, COMPOSE_OVERRIDE_FILE


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
    def test_no_overrides(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {})
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        assert not override_file.exists()

    def test_cpu_limit(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_CPU_LIMIT": "2.0",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        assert override_file.exists()
        content = override_file.read_text()
        assert "cpus" in content
        assert "2.0" in content

    def test_mem_limit(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_MEM_LIMIT": "4g",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        assert override_file.exists()
        content = override_file.read_text()
        assert "memory" in content

    def test_hardened_mode(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_HARDENED_MODE": "true",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        assert override_file.exists()
        content = override_file.read_text()
        assert "read_only" in content
        assert "cap_drop" in content
        assert "tmpfs" in content

    def test_proxy_mode_override(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_PROXY_MODE": "proxy",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        assert override_file.exists()
        content = override_file.read_text()
        assert "HTTP_PROXY" in content
        assert "HTTPS_PROXY" in content
        assert "proxy_certs" in content

    def test_cleanup_when_no_overrides(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        override_file.write_text("old content")
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {})
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        assert not override_file.exists()
