"""Shared test fixtures."""

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with minimal structure."""
    project = tmp_path / "sandbox"
    project.mkdir()

    # Config
    config_dir = project / "config" / "tools"
    config_dir.mkdir(parents=True)

    # Docker
    fw_dir = project / "docker" / "firewall"
    fw_dir.mkdir(parents=True)
    (fw_dir / "whitelist.txt").write_text("registry.npmjs.org\n")

    # .env.dist
    (project / ".env.dist").write_text(
        "COMPOSE_PROJECT_NAME=project\n"
        "TZ=\n"
        "SANDBOX_LOG_DIR=./logs\n"
        "SANDBOX_LOG_RETENTION_DAYS=30\n"
    )

    return project


@pytest.fixture
def tool_definition(tmp_project):
    """Create a sample tool definition."""
    tool_file = tmp_project / "config" / "tools" / "test-tool.yaml"
    tool_file.write_text(
        "name: test-tool\n"
        "description: A test tool\n"
        "default: false\n"
        "install:\n"
        "  method: npm\n"
        "  package: test-package\n"
        "  global: true\n"
        "firewall:\n"
        "  domains:\n"
        "    - api.test.com\n"
        "    - cdn.test.com\n"
        "env:\n"
        "  TEST_API_KEY: ''\n"
    )
    return tool_file


@pytest.fixture
def whitelist_file(tmp_project):
    """Return the whitelist file path."""
    return tmp_project / "docker" / "firewall" / "whitelist.txt"
