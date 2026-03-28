"""E2E: Layer 4 - Secrets and Config."""

import json

from test.e2e.conftest import sandbox, sandbox_output, E2E_DATA_DIR


class TestSecretsCLI:
    def test_set_and_get(self):
        sandbox("secrets", "set", "E2E_TEST_KEY", "e2e_test_value", check=True)
        output = sandbox_output("secrets", "get", "E2E_TEST_KEY", "--show")
        assert "e2e_test_value" in output

    def test_masked_by_default(self):
        sandbox("secrets", "set", "E2E_MASK_KEY", "super_secret_12345", check=True)
        output = sandbox_output("secrets", "get", "E2E_MASK_KEY")
        assert "super_secret_12345" not in output
        assert "****" in output or "**" in output

    def test_list_keys(self):
        sandbox("secrets", "set", "E2E_LIST_KEY", "value", check=True)
        output = sandbox_output("secrets", "list")
        assert "E2E_LIST_KEY" in output

    def test_delete(self):
        sandbox("secrets", "set", "E2E_DELETE_KEY", "value", check=True)
        sandbox("secrets", "delete", "E2E_DELETE_KEY", check=True)
        result = sandbox("secrets", "get", "E2E_DELETE_KEY",
                         capture_output=True, text=True)
        assert result.returncode != 0

    def test_special_characters(self):
        sandbox("secrets", "set", "E2E_SPECIAL", "p@ss w0rd!#$%", check=True)
        output = sandbox_output("secrets", "get", "E2E_SPECIAL", "--show")
        assert "p@ss w0rd!#$%" in output
        sandbox("secrets", "delete", "E2E_SPECIAL", check=True)

    def test_overwrite(self):
        sandbox("secrets", "set", "E2E_OVERWRITE", "old", check=True)
        sandbox("secrets", "set", "E2E_OVERWRITE", "new", check=True)
        output = sandbox_output("secrets", "get", "E2E_OVERWRITE", "--show")
        assert "new" in output
        sandbox("secrets", "delete", "E2E_OVERWRITE", check=True)

    def test_cleanup(self):
        for key in ["E2E_TEST_KEY", "E2E_MASK_KEY", "E2E_LIST_KEY"]:
            sandbox("secrets", "delete", key, capture_output=True)


class TestConfigCLI:
    def test_show(self):
        output = sandbox_output("config", "show")
        assert "COMPOSE_PROJECT_NAME" in output

    def test_show_path(self):
        output = sandbox_output("config", "show", "--path")
        assert "sandbox" in output

    def test_set_and_get(self):
        sandbox("config", "set", "SANDBOX_LOG_FORMAT", "json", check=True)
        output = sandbox_output("config", "get", "SANDBOX_LOG_FORMAT")
        assert "json" in output
        # Restore
        sandbox("config", "set", "SANDBOX_LOG_FORMAT", "text", check=True)

    def test_get_nonexistent(self):
        result = sandbox("config", "get", "NONEXISTENT_KEY_12345",
                         capture_output=True, text=True)
        assert result.returncode != 0

    def test_profiles(self):
        result = sandbox("config", "profiles", capture_output=True, text=True)
        assert result.returncode == 0

    def test_create_profile(self):
        sandbox("config", "create-profile", "e2e-test", capture_output=True)
        output = sandbox_output("config", "profiles")
        assert "e2e-test" in output


class TestConfigExportImport:
    def test_export(self):
        output_file = E2E_DATA_DIR / "e2e-config-export.json"
        sandbox("config", "export", "-o", str(output_file), check=True)

        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "env" in data
        assert "tools" in data
        output_file.unlink()

    def test_data_dir_override(self):
        output = sandbox_output("config", "show", "--path")
        assert str(E2E_DATA_DIR) in output
