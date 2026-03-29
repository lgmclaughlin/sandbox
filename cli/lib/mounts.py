"""Mount management: rclone and sshfs mounting."""

import subprocess
from pathlib import Path

import cli.lib.config as config
from cli.lib.paths import get_data_dir
from cli.lib.platform import IS_WINDOWS, check_rclone, check_sshfs


def setup_mounts(workspace: Path | None = None) -> list[dict]:
    """Set up all configured mounts. Returns list of mount results.

    Relative local paths are resolved against the workspace directory.
    If any mount fails, successfully mounted paths are rolled back.
    If a path is already mounted by another process, refuses with an error.
    """
    mounts = config.load_mounts()
    if not mounts:
        return []

    results = []
    mounted_paths = []  # Track successful mounts for rollback

    for mount in mounts:
        name = mount.get("name", "unnamed")
        mount_type = mount.get("type", "rclone")
        remote = mount.get("remote", "")
        local = mount.get("local", "")
        options = mount.get("options", {})

        if not remote or not local:
            results.append({"name": name, "ok": False, "error": "Missing remote or local path"})
            _rollback_mounts(mounted_paths)
            return results

        local_path = Path(local)
        if not local_path.is_absolute():
            if workspace:
                local_path = workspace / local_path
            else:
                local_path = Path.cwd() / local_path

        # If already mounted, check if it's the same remote (same project restarting)
        # or a different remote (conflict from another project)
        if _is_mounted(local_path):
            existing_source = _get_mount_source(local_path)
            if existing_source and remote.split(":")[0] in existing_source:
                # Same remote, reuse the mount
                results.append({"name": name, "ok": True, "error": ""})
                continue
            else:
                results.append({"name": name, "ok": False,
                                "error": f"Already mounted at {local_path} by another source ({existing_source}). "
                                         f"Run 'sandbox mount clear {local_path}' to unmount."})
                _rollback_mounts(mounted_paths)
                return results

        local_path.mkdir(parents=True, exist_ok=True)

        if mount_type == "rclone":
            ok, error = _mount_rclone(remote, local_path, options)
        elif mount_type == "sshfs":
            ok, error = _mount_sshfs(remote, local_path, options)
        else:
            ok, error = False, f"Unknown mount type: {mount_type}"

        if ok:
            mounted_paths.append(local_path)
        else:
            results.append({"name": name, "ok": False, "error": error})
            _rollback_mounts(mounted_paths)
            return results

        results.append({"name": name, "ok": True, "error": ""})

    return results


def _rollback_mounts(paths: list[Path]) -> None:
    """Unmount any successfully mounted paths during a failed setup."""
    for path in paths:
        _unmount(path)


def _get_mount_source(path: Path) -> str:
    """Get the source of a mount at the given path from the system mount table."""
    try:
        result = subprocess.run(
            ["findmnt", "-n", "-o", "SOURCE", str(path)],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _is_mounted(path: Path) -> bool:
    """Check if a path is already a mount point."""
    if IS_WINDOWS:
        return path.exists() and any(path.iterdir())

    try:
        result = subprocess.run(
            ["mountpoint", "-q", str(path)],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _mount_rclone(remote: str, local: Path, options: dict) -> tuple[bool, str]:
    """Mount via rclone. Returns (success, error_message)."""
    if not check_rclone():
        return False, "rclone is not installed"

    if _is_mounted(local):
        return True, ""

    cmd = ["rclone", "mount", remote, str(local), "--daemon",
           "--vfs-cache-mode", "writes"]

    for key, value in options.items():
        if isinstance(value, bool):
            if value:
                cmd.append(f"--{key}")
        else:
            cmd.extend([f"--{key}", str(value)])

    try:
        # Try with daemon (works if no passphrase or agent is loaded)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return True, ""

        # If key passphrase is the issue, prompt and retry
        stderr = result.stderr or ""
        if "passphrase protected" in stderr or "private key" in stderr:
            import getpass
            mount_name = local.name or remote.split(":")[0]
            passphrase = getpass.getpass(f"  Passphrase for {mount_name} ({remote.split(':')[0]}): ")

            # rclone expects obscured passwords, not plaintext
            obscured = subprocess.run(
                ["rclone", "obscure", passphrase],
                capture_output=True, text=True,
            )
            if obscured.returncode != 0:
                return False, "Failed to obscure passphrase"

            cmd_with_pass = [*cmd, "--sftp-key-file-pass", obscured.stdout.strip()]
            result = subprocess.run(cmd_with_pass, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True, ""
            return False, result.stderr.strip() or f"Mount failed (exit {result.returncode})"

        return False, stderr.strip() or f"rclone mount failed (exit {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "Mount timed out"
    except FileNotFoundError:
        return False, "rclone not found"


def _mount_sshfs(remote: str, local: Path, options: dict) -> tuple[bool, str]:
    """Mount via sshfs. Returns (success, error_message)."""
    if not check_sshfs():
        return False, "sshfs is not installed"

    if _is_mounted(local):
        return True, ""

    sshfs_cmd = "sshfs.exe" if IS_WINDOWS else "sshfs"
    cmd = [sshfs_cmd, remote, str(local)]

    default_opts = ["reconnect", "ServerAliveInterval=15", "ServerAliveCountMax=3"]
    opt_strings = list(default_opts)

    for key, value in options.items():
        if isinstance(value, bool):
            if value:
                opt_strings.append(key)
        else:
            opt_strings.append(f"{key}={value}")

    if opt_strings:
        cmd.extend(["-o", ",".join(opt_strings)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Mount timed out"
    except FileNotFoundError:
        return False, "sshfs not found"


def unmount_all() -> None:
    """Unmount all configured mounts."""
    mounts = config.load_mounts()
    for mount in mounts:
        local = mount.get("local", "")
        if not local:
            continue

        local_path = Path(local)
        if not local_path.is_absolute():
            local_path = Path.cwd() / local_path

        if _is_mounted(local_path):
            _unmount(local_path)


def _unmount(path: Path) -> None:
    """Unmount a path."""
    from cli.lib.platform import IS_MACOS

    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/IM", "rclone.exe"], capture_output=True)
    elif IS_MACOS:
        subprocess.run(["umount", str(path)], capture_output=True)
    else:
        # Try fusermount3 first (Arch, newer distros), fall back to fusermount
        import shutil
        fuse_cmd = "fusermount3" if shutil.which("fusermount3") else "fusermount"
        subprocess.run([fuse_cmd, "-u", "-z", str(path)], capture_output=True)
