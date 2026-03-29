"""E2E: Mount management and conflict detection."""

import subprocess
import time
from pathlib import Path

import pytest

from test.e2e.conftest import sandbox, sandbox_output, E2E_DATA_DIR


class TestMountCLI:
    def test_add_mount(self):
        sandbox("mount", "add", "test-rclone",
                "--type", "rclone", "--remote", "test:/path", "--local", "./test-dir",
                check=True)

        output = sandbox_output("mount", "list")
        assert "test-rclone" in output
        assert "rclone" in output

    def test_add_sshfs_mount(self):
        sandbox("mount", "add", "test-sshfs",
                "--type", "sshfs", "--remote", "test@host:/path", "--local", "./test-sshfs-dir",
                check=True)

        output = sandbox_output("mount", "list")
        assert "test-sshfs" in output
        assert "sshfs" in output

    def test_add_duplicate_rejected(self):
        result = sandbox("mount", "add", "test-rclone",
                         "--type", "rclone", "--remote", "test:/other", "--local", "./other",
                         capture_output=True, text=True)
        assert result.returncode != 0
        assert "already exists" in result.stdout or "already exists" in result.stderr

    def test_remove_mount(self):
        sandbox("mount", "remove", "test-rclone", check=True)
        sandbox("mount", "remove", "test-sshfs", check=True)

        output = sandbox_output("mount", "list")
        assert "test-rclone" not in output
        assert "test-sshfs" not in output

    def test_remove_nonexistent(self):
        result = sandbox("mount", "remove", "ghost-mount",
                         capture_output=True, text=True)
        assert result.returncode != 0

    def test_list_empty(self):
        output = sandbox_output("mount", "list")
        assert "No mounts" in output or "test-rclone" not in output


class TestMountConflictDetection:
    """Tests that verify mount collision handling.

    These tests create real FUSE mounts using rclone's local backend
    (no remote server needed) to test collision detection and rollback.
    """

    @pytest.fixture(autouse=True)
    def setup_local_mounts(self, tmp_path):
        """Set up test directories for local rclone mounts."""
        self.source_a = tmp_path / "source_a"
        self.source_b = tmp_path / "source_b"
        self.mount_a = tmp_path / "mount_a"
        self.mount_b = tmp_path / "mount_b"

        self.source_a.mkdir()
        self.source_b.mkdir()
        self.mount_a.mkdir()
        self.mount_b.mkdir()

        (self.source_a / "file_a.txt").write_text("from source a")
        (self.source_b / "file_b.txt").write_text("from source b")

        yield

        # Cleanup any mounts
        for mount in [self.mount_a, self.mount_b]:
            subprocess.run(["fusermount3", "-u", str(mount)], capture_output=True)

    def _local_rclone_mount(self, source: Path, target: Path) -> bool:
        """Mount a local directory via rclone (no remote needed)."""
        result = subprocess.run(
            ["rclone", "mount", f":local:{source}", str(target), "--daemon",
             "--vfs-cache-mode", "writes"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return False
        time.sleep(1)
        return True

    def test_detects_already_mounted_path(self):
        """If a path is already mounted, setup_mounts should refuse."""
        from cli.lib.mounts import _is_mounted

        assert not _is_mounted(self.mount_a)

        ok = self._local_rclone_mount(self.source_a, self.mount_a)
        if not ok:
            pytest.skip("rclone local mount not available")

        assert _is_mounted(self.mount_a)

    def test_same_remote_reuses_mount(self):
        """If the same remote is already mounted, it should be reused."""
        from cli.lib.mounts import setup_mounts, _is_mounted

        ok = self._local_rclone_mount(self.source_a, self.mount_a)
        if not ok:
            pytest.skip("rclone local mount not available")
        time.sleep(2)
        assert _is_mounted(self.mount_a)

        import cli.lib.config as config
        original_load = config.load_mounts

        def mock_mounts():
            return [
                {"name": "mount-a", "type": "rclone",
                 "remote": f":local:{self.source_a}", "local": str(self.mount_a)},
            ]

        config.load_mounts = mock_mounts
        try:
            results = setup_mounts()
            assert all(r["ok"] for r in results), "Same remote should reuse mount"
        finally:
            config.load_mounts = original_load

    def test_different_remote_refuses(self):
        """If a different remote is mounted at the path, it should refuse and rollback."""
        from cli.lib.mounts import setup_mounts, _is_mounted

        # Mount source_a at mount_b's path (simulating another project)
        ok = self._local_rclone_mount(self.source_a, self.mount_b)
        if not ok:
            pytest.skip("rclone local mount not available")
        time.sleep(2)
        assert _is_mounted(self.mount_b)

        import cli.lib.config as config
        original_load = config.load_mounts

        def mock_mounts():
            return [
                {"name": "mount-a", "type": "rclone",
                 "remote": f":local:{self.source_a}", "local": str(self.mount_a)},
                {"name": "mount-b", "type": "rclone",
                 "remote": "different-remote:/other/path", "local": str(self.mount_b)},
            ]

        config.load_mounts = mock_mounts
        try:
            results = setup_mounts()
            failed = [r for r in results if not r["ok"]]
            assert len(failed) > 0
            assert "Already mounted" in failed[0]["error"]
        finally:
            config.load_mounts = original_load
            subprocess.run(["fusermount3", "-u", str(self.mount_a)], capture_output=True)
            subprocess.run(["fusermount3", "-u", str(self.mount_b)], capture_output=True)
