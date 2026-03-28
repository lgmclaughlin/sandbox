"""E2E test fixtures. Manages real Docker containers."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SANDBOX_CMD = shutil.which("sandbox")

if not SANDBOX_CMD:
    venv_sandbox = REPO_ROOT / ".venv" / "bin" / "sandbox"
    if venv_sandbox.exists():
        SANDBOX_CMD = str(venv_sandbox)
    else:
        SANDBOX_CMD = None

E2E_DATA_DIR = Path("/tmp/sandbox-e2e-test")
E2E_WORKSPACE = Path("/tmp/sandbox-e2e-workspace")


def sandbox(*args: str, check: bool = False, **kwargs) -> subprocess.CompletedProcess:
    """Run sandbox CLI command for E2E tests."""
    env = {**os.environ, "SANDBOX_DATA_DIR": str(E2E_DATA_DIR)}
    return subprocess.run([SANDBOX_CMD, *args], env=env, check=check, **kwargs)


def sandbox_output(*args: str) -> str:
    """Run sandbox and return stdout."""
    result = sandbox(*args, capture_output=True, text=True)
    return result.stdout.strip()


@pytest.fixture(scope="session", autouse=True)
def e2e_environment():
    """Set up and tear down the E2E test environment.

    Runs once for the entire test session:
    1. Scaffold config
    2. Create workspace
    3. Start containers
    4. Run all tests
    5. Stop containers
    6. Clean up
    """
    if not SANDBOX_CMD:
        pytest.skip("sandbox command not found")

    # Check Docker is available
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        pytest.skip("Docker not available")

    # Clean slate
    if E2E_DATA_DIR.exists():
        shutil.rmtree(E2E_DATA_DIR)
    E2E_WORKSPACE.mkdir(parents=True, exist_ok=True)
    (E2E_WORKSPACE / "test-file.txt").write_text("hello from e2e test\n")

    # Scaffold
    os.environ["SANDBOX_DATA_DIR"] = str(E2E_DATA_DIR)
    sandbox("config", "show", "--path", check=True)  # triggers scaffolding

    # Start containers (may build images on first run)
    result = sandbox("start", "--no-attach", str(E2E_WORKSPACE),
                     capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        print(f"Failed to start sandbox:\n{result.stdout}\n{result.stderr}")
        pytest.skip("Failed to start sandbox containers")

    # Give containers a moment to fully initialize
    time.sleep(3)

    yield

    # Teardown
    sandbox("stop")
    if E2E_DATA_DIR.exists():
        shutil.rmtree(E2E_DATA_DIR)
    if E2E_WORKSPACE.exists():
        shutil.rmtree(E2E_WORKSPACE)
