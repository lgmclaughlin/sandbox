"""Integration tests for first-run scaffolding."""

from cli.lib.scaffold import scaffold, is_scaffolded


class TestScaffolding:
    def test_scaffold_creates_structure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.scaffold.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("cli.lib.paths.get_data_dir", lambda: tmp_path)

        assert not is_scaffolded()

        path = scaffold()
        assert path == tmp_path
        assert is_scaffolded()

        assert (tmp_path / ".env").exists()
        assert (tmp_path / ".env.dist").exists()
        assert (tmp_path / "config" / "tools" / "claude-code.yaml").exists()
        assert (tmp_path / "config" / "mcp" / "filesystem.yaml").exists()
        assert (tmp_path / "config" / "firewall" / "profiles" / "dev.yaml").exists()
        assert (tmp_path / "docker" / "Dockerfile").exists()
        assert (tmp_path / "docker" / "docker-compose.yml").exists()
        assert (tmp_path / "docker" / "entrypoint.sh").exists()
        assert (tmp_path / "docker" / "mcp-log-wrapper.py").exists()
        assert (tmp_path / "docker" / "firewall" / "firewall-init.sh").exists()
        assert (tmp_path / "logs" / "sessions").exists()
        assert (tmp_path / "logs" / "commands").exists()

    def test_scaffold_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.scaffold.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("cli.lib.paths.get_data_dir", lambda: tmp_path)

        scaffold()
        env_content = (tmp_path / ".env").read_text()

        (tmp_path / ".env").write_text(env_content + "\nCUSTOM_VAR=custom\n")

        scaffold()
        assert "CUSTOM_VAR=custom" in (tmp_path / ".env").read_text()

    def test_scaffold_force(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cli.lib.scaffold.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("cli.lib.paths.get_data_dir", lambda: tmp_path)

        scaffold()
        (tmp_path / ".env.dist").write_text("MODIFIED=true\n")

        scaffold(force=True)
        content = (tmp_path / ".env.dist").read_text()
        assert "MODIFIED" not in content
        assert "COMPOSE_PROJECT_NAME" in content
