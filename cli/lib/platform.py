"""Platform detection and compatibility helpers."""

import shutil
import platform


PLATFORM = platform.system().lower()  # "linux", "darwin", "windows"
IS_LINUX = PLATFORM == "linux"
IS_MACOS = PLATFORM == "darwin"
IS_WINDOWS = PLATFORM == "windows"


def check_docker() -> str | None:
    """Check if Docker is available. Returns error message or None if OK."""
    if not shutil.which("docker"):
        return "Docker is not installed or not in PATH"

    if IS_WINDOWS and not shutil.which("docker.exe"):
        return "Docker Desktop for Windows is required"

    return None


def check_rclone() -> bool:
    """Check if rclone is available on the host."""
    return shutil.which("rclone") is not None


def check_sshfs() -> bool:
    """Check if sshfs is available on the host."""
    cmd = "sshfs.exe" if IS_WINDOWS else "sshfs"
    return shutil.which(cmd) is not None


def get_user_info() -> dict[str, str]:
    """Get current user info for audit logging."""
    import getpass
    import socket

    return {
        "user": getpass.getuser(),
        "hostname": socket.gethostname(),
        "platform": PLATFORM,
    }
