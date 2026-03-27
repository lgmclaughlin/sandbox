"""Integration tests for resource limits and hardened mode."""

import yaml

from cli.lib.docker import _generate_override


class TestResourceLimits:
    def test_no_limits_no_override(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {})
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        assert not override_file.exists()

    def test_cpu_and_mem_limits(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_CPU_LIMIT": "2.0",
            "SANDBOX_MEM_LIMIT": "4g",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        data = yaml.safe_load(override_file.read_text())
        limits = data["services"]["sandbox"]["deploy"]["resources"]["limits"]
        assert limits["cpus"] == "2.0"
        assert limits["memory"] == "4g"

    def test_hardened_mode_full(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_HARDENED_MODE": "true",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        data = yaml.safe_load(override_file.read_text())
        sandbox = data["services"]["sandbox"]
        assert sandbox["read_only"] is True
        assert "ALL" in sandbox["cap_drop"]
        assert any("/tmp" in t for t in sandbox["tmpfs"])
        assert any("/home/node" in t for t in sandbox["tmpfs"])

    def test_combined_limits_and_hardened(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_CPU_LIMIT": "1.0",
            "SANDBOX_MEM_LIMIT": "2g",
            "SANDBOX_HARDENED_MODE": "true",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        data = yaml.safe_load(override_file.read_text())
        sandbox = data["services"]["sandbox"]

        assert sandbox["deploy"]["resources"]["limits"]["cpus"] == "1.0"
        assert sandbox["read_only"] is True
        assert "ALL" in sandbox["cap_drop"]

    def test_proxy_mode_adds_env_and_certs(self, tmp_path, monkeypatch):
        override_file = tmp_path / "override.yml"
        monkeypatch.setattr("cli.lib.docker.COMPOSE_OVERRIDE_FILE", override_file)
        monkeypatch.setattr("cli.lib.docker.load_env", lambda: {
            "SANDBOX_PROXY_MODE": "proxy",
        })
        monkeypatch.setattr("cli.lib.docker.PROJECT_ROOT", tmp_path)

        _generate_override()
        data = yaml.safe_load(override_file.read_text())
        sandbox = data["services"]["sandbox"]

        env_list = sandbox["environment"]
        assert any("HTTP_PROXY" in e for e in env_list)
        assert any("HTTPS_PROXY" in e for e in env_list)
        assert any("proxy_certs" in v for v in sandbox["volumes"])
