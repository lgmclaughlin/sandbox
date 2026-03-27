"""Unit tests for CLI argument parsing and validation."""

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


class TestCLIHelp:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Secure AI development environment" in result.output

    def test_fw_help(self):
        result = runner.invoke(app, ["fw", "--help"])
        assert result.exit_code == 0
        assert "ls" in result.output
        assert "add" in result.output
        assert "remove" in result.output

    def test_tool_help(self):
        result = runner.invoke(app, ["tool", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "install" in result.output
        assert "remove" in result.output


class TestVersion:
    def test_version_output(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "sandbox version" in result.output


class TestFwValidation:
    def test_add_requires_domain(self):
        result = runner.invoke(app, ["fw", "add"])
        assert result.exit_code != 0

    def test_add_invalid_domain(self):
        result = runner.invoke(app, ["fw", "add", "not a domain!"])
        assert result.exit_code != 0
        assert "Invalid domain" in result.output

    def test_remove_requires_domain(self):
        result = runner.invoke(app, ["fw", "remove"])
        assert result.exit_code != 0


class TestToolValidation:
    def test_install_requires_name(self):
        result = runner.invoke(app, ["tool", "install"])
        assert result.exit_code != 0

    def test_remove_requires_name(self):
        result = runner.invoke(app, ["tool", "remove"])
        assert result.exit_code != 0


class TestFwLs:
    def test_lists_domains(self):
        result = runner.invoke(app, ["fw", "ls"])
        assert result.exit_code == 0

    def test_tool_list(self):
        result = runner.invoke(app, ["tool", "list"])
        assert result.exit_code == 0
