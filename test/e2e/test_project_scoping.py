"""E2E: Project-scoped command isolation.

Verifies that --project flag correctly scopes config, mounts,
tools, secrets, and other commands to the named project.
"""

from test.e2e.conftest import sandbox, sandbox_output, E2E_DATA_DIR


class TestProjectMountScoping:
    def test_mount_add_to_project(self):
        sandbox("init", "mount-test", capture_output=True)

        sandbox("--project", "mount-test", "mount", "add", "test-mount",
                "--type", "rclone", "--remote", "test:/path", "--local", "./data",
                check=True)

        output = sandbox_output("--project", "mount-test", "mount", "list")
        assert "test-mount" in output

    def test_mount_not_in_default(self):
        output = sandbox_output("mount", "list")
        assert "test-mount" not in output

    def test_mount_remove_from_project(self):
        sandbox("--project", "mount-test", "mount", "remove", "test-mount", check=True)
        output = sandbox_output("--project", "mount-test", "mount", "list")
        assert "test-mount" not in output

    def test_cleanup(self):
        sandbox("remove-project", "mount-test", "--yes", capture_output=True)


class TestProjectConfigScoping:
    def test_config_set_to_project(self):
        sandbox("init", "config-test", capture_output=True)

        sandbox("--project", "config-test", "config", "set",
                "SANDBOX_LOG_FORMAT", "json", check=True)

        output = sandbox_output("--project", "config-test", "config", "get", "SANDBOX_LOG_FORMAT")
        assert "json" in output

    def test_config_not_in_default(self):
        output = sandbox_output("config", "get", "SANDBOX_LOG_FORMAT")
        assert "text" in output

    def test_cleanup(self):
        sandbox("remove-project", "config-test", "--yes", capture_output=True)


class TestProjectToolScoping:
    def test_tool_add_to_project(self):
        sandbox("init", "tool-test", capture_output=True)

        sandbox("--project", "tool-test", "tool", "add", "custom-tool",
                "--method", "pip", "--package", "custom-pkg",
                check=True)

        output = sandbox_output("--project", "tool-test", "tool", "list")
        assert "custom-tool" in output

    def test_tool_not_in_default(self):
        output = sandbox_output("tool", "list")
        assert "custom-tool" not in output

    def test_cleanup(self):
        sandbox("remove-project", "tool-test", "--yes", capture_output=True)


class TestProjectSecretsScoping:
    def test_secret_set_in_project(self):
        sandbox("init", "secret-test", capture_output=True)

        sandbox("--project", "secret-test", "secrets", "set",
                "PROJECT_KEY", "project_value", check=True)

        output = sandbox_output("--project", "secret-test", "secrets", "get",
                                "PROJECT_KEY", "--show")
        assert "project_value" in output

    def test_secret_not_in_default(self):
        result = sandbox("secrets", "get", "PROJECT_KEY",
                         capture_output=True, text=True)
        assert result.returncode != 0

    def test_cleanup(self):
        sandbox("remove-project", "secret-test", "--yes", capture_output=True)


class TestProjectLogFilterScoping:
    def test_log_filter_in_project(self):
        sandbox("init", "filter-test", capture_output=True)

        sandbox("--project", "filter-test", "logs", "filter",
                "sessions,commands", check=True)

        output = sandbox_output("--project", "filter-test", "logs", "filter")
        assert "sessions,commands" in output

    def test_log_filter_default_unchanged(self):
        output = sandbox_output("logs", "filter")
        assert "all" in output

    def test_cleanup(self):
        sandbox("remove-project", "filter-test", "--yes", capture_output=True)
