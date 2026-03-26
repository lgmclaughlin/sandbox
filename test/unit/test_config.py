"""Unit tests for config lib functions."""

from pathlib import Path

from cli.lib.config import (
    detect_timezone,
    ensure_env,
    ensure_mounts_config,
    load_env,
    load_mounts,
    load_tool_definition,
    list_available_tools,
    get_default_tool,
)


class TestLoadEnv:
    def test_load_existing(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")
        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)

        env = load_env()
        assert env["FOO"] == "bar"
        assert env["BAZ"] == "qux"

    def test_load_missing(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        dist_file = tmp_path / ".env.dist"
        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist_file)

        assert load_env() == {}

    def test_skips_empty_values(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FILLED=yes\nEMPTY=\n")
        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)

        env = load_env()
        assert env["FILLED"] == "yes"
        assert env.get("EMPTY") == ""


class TestEnsureEnv:
    def test_copies_dist_if_missing(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=project\nTZ=UTC\n")
        env_file = tmp_path / ".env"

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)

        result = ensure_env()
        assert env_file.exists()
        assert "COMPOSE_PROJECT_NAME" in result

    def test_does_not_overwrite_existing(self, tmp_path, monkeypatch):
        dist = tmp_path / ".env.dist"
        dist.write_text("COMPOSE_PROJECT_NAME=default\n")
        env_file = tmp_path / ".env"
        env_file.write_text("COMPOSE_PROJECT_NAME=custom\n")

        monkeypatch.setattr("cli.lib.config.ENV_FILE", env_file)
        monkeypatch.setattr("cli.lib.config.ENV_DIST_FILE", dist)

        result = ensure_env()
        assert result["COMPOSE_PROJECT_NAME"] == "custom"


class TestLoadMounts:
    def test_empty_file(self, tmp_path, monkeypatch):
        mounts_file = tmp_path / "mounts.yaml"
        mounts_file.write_text("")
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)

        assert load_mounts() == []

    def test_empty_list(self, tmp_path, monkeypatch):
        mounts_file = tmp_path / "mounts.yaml"
        mounts_file.write_text("mounts: []\n")
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)

        assert load_mounts() == []

    def test_missing_file(self, tmp_path, monkeypatch):
        mounts_file = tmp_path / "mounts.yaml"
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)

        assert load_mounts() == []

    def test_valid_mounts(self, tmp_path, monkeypatch):
        mounts_file = tmp_path / "mounts.yaml"
        mounts_file.write_text(
            "mounts:\n"
            "  - name: test\n"
            "    type: rclone\n"
            "    remote: s3:bucket/path\n"
            "    local: ./workspace/test\n"
        )
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)

        mounts = load_mounts()
        assert len(mounts) == 1
        assert mounts[0]["name"] == "test"
        assert mounts[0]["type"] == "rclone"


class TestEnsureMountsConfig:
    def test_creates_if_missing(self, tmp_path, monkeypatch):
        mounts_file = tmp_path / "config" / "mounts.yaml"
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)

        ensure_mounts_config()
        assert mounts_file.exists()
        assert load_mounts() == []

    def test_does_not_overwrite_existing(self, tmp_path, monkeypatch):
        mounts_file = tmp_path / "mounts.yaml"
        mounts_file.write_text(
            "mounts:\n"
            "  - name: existing\n"
            "    type: sshfs\n"
            "    remote: user@host:/path\n"
            "    local: ./workspace/existing\n"
        )
        monkeypatch.setattr("cli.lib.config.MOUNTS_FILE", mounts_file)

        ensure_mounts_config()
        mounts = load_mounts()
        assert len(mounts) == 1
        assert mounts[0]["name"] == "existing"


class TestToolDefinitions:
    def test_load_existing(self, tmp_path, monkeypatch):
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "my-tool.yaml").write_text(
            "name: my-tool\n"
            "description: Test tool\n"
            "default: true\n"
        )
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tools_dir)

        tool = load_tool_definition("my-tool")
        assert tool is not None
        assert tool["name"] == "my-tool"
        assert tool["default"] is True

    def test_load_missing(self, tmp_path, monkeypatch):
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tools_dir)

        assert load_tool_definition("nonexistent") is None

    def test_list_available(self, tmp_path, monkeypatch):
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "a.yaml").write_text("name: a\ndescription: Tool A\n")
        (tools_dir / "b.yaml").write_text("name: b\ndescription: Tool B\n")
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tools_dir)

        tools = list_available_tools()
        assert len(tools) == 2
        names = [t["name"] for t in tools]
        assert "a" in names
        assert "b" in names

    def test_get_default(self, tmp_path, monkeypatch):
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "a.yaml").write_text("name: a\ndefault: false\n")
        (tools_dir / "b.yaml").write_text("name: b\ndefault: true\n")
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tools_dir)

        default = get_default_tool()
        assert default is not None
        assert default["name"] == "b"

    def test_no_default(self, tmp_path, monkeypatch):
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "a.yaml").write_text("name: a\ndefault: false\n")
        monkeypatch.setattr("cli.lib.config.TOOLS_DIR", tools_dir)

        assert get_default_tool() is None


class TestDetectTimezone:
    def test_respects_env_var(self, monkeypatch):
        monkeypatch.setenv("TZ", "America/New_York")
        assert detect_timezone() == "America/New_York"

    def test_returns_something(self, monkeypatch):
        monkeypatch.delenv("TZ", raising=False)
        tz = detect_timezone()
        assert isinstance(tz, str)
        assert len(tz) > 0
