"""Mount management: rclone and sshfs mounting."""

import subprocess
from pathlib import Path

from cli.lib.config import PROJECT_ROOT, load_mounts
from cli.lib.platform import IS_WINDOWS, check_rclone, check_sshfs


def setup_mounts() -> list[dict]:
    """Set up all configured mounts. Returns list of mount results."""
    mounts = load_mounts()
    if not mounts:
        return []

    results = []
    for mount in mounts:
        name = mount.get("name", "unnamed")
        mount_type = mount.get("type", "rclone")
        remote = mount.get("remote", "")
        local = mount.get("local", "")
        options = mount.get("options", {})

        if not remote or not local:
            results.append({"name": name, "ok": False, "error": "Missing remote or local path"})
            continue

        local_path = Path(local)
        if not local_path.is_absolute():
            local_path = PROJECT_ROOT / local_path

        local_path.mkdir(parents=True, exist_ok=True)

        if mount_type == "rclone":
            ok, error = _mount_rclone(remote, local_path, options)
        elif mount_type == "sshfs":
            ok, error = _mount_sshfs(remote, local_path, options)
        else:
            ok, error = False, f"Unknown mount type: {mount_type}"

        results.append({"name": name, "ok": ok, "error": error})

    return results


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

    cmd = ["rclone", "mount", remote, str(local), "--daemon"]

    for key, value in options.items():
        if isinstance(value, bool):
            if value:
                cmd.append(f"--{key}")
        else:
            cmd.extend([f"--{key}", str(value)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, ""
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
    mounts = load_mounts()
    for mount in mounts:
        local = mount.get("local", "")
        if not local:
            continue

        local_path = Path(local)
        if not local_path.is_absolute():
            local_path = PROJECT_ROOT / local_path

        if _is_mounted(local_path):
            _unmount(local_path)


def _unmount(path: Path) -> None:
    """Unmount a path."""
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/F", "/IM", "rclone.exe"], capture_output=True)
    else:
        subprocess.run(["fusermount", "-u", "-z", str(path)], capture_output=True)
