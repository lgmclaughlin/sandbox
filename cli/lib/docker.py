"""Docker container management via Docker SDK."""

import os
import subprocess
import sys
from pathlib import Path

import docker
from docker.errors import DockerException, NotFound

from cli.lib.config import PROJECT_ROOT, load_env

COMPOSE_FILE = PROJECT_ROOT / "docker" / "docker-compose.yml"
FIREWALL_SERVICE = "firewall"
SANDBOX_SERVICE = "sandbox"


def _get_project_name() -> str:
    env = load_env()
    return env.get("COMPOSE_PROJECT_NAME", "project")


def _container_name(service: str) -> str:
    return f"{_get_project_name()}_{service}"


def _get_client() -> docker.DockerClient:
    try:
        return docker.from_env()
    except DockerException as e:
        raise SystemExit(f"Cannot connect to Docker: {e}")


def _get_container(client: docker.DockerClient, service: str):
    try:
        return client.containers.get(_container_name(service))
    except NotFound:
        return None


def _compose_cmd() -> list[str]:
    env = load_env()
    project = env.get("COMPOSE_PROJECT_NAME", "project")
    return [
        "docker", "compose",
        "-p", project,
        "-f", str(COMPOSE_FILE),
    ]


def _compose_env() -> dict[str, str]:
    """Build environment for docker compose commands."""
    env = {**os.environ, **load_env()}
    env.setdefault("USER_ID", str(os.getuid()))
    env.setdefault("GROUP_ID", str(os.getgid()))
    return env


def is_running(service: str) -> bool:
    client = _get_client()
    container = _get_container(client, service)
    return container is not None and container.status == "running"


def start_containers(build: bool = False) -> None:
    """Start firewall and sandbox containers."""
    env = _compose_env()
    base = _compose_cmd()

    if not is_running(FIREWALL_SERVICE):
        subprocess.run([*base, "up", "-d", FIREWALL_SERVICE], env=env, check=True)

    if build or not is_running(FIREWALL_SERVICE):
        _init_firewall()

    if build:
        subprocess.run([*base, "build", SANDBOX_SERVICE], env=env, check=True)

    subprocess.run([*base, "up", "-d", SANDBOX_SERVICE], env=env, check=True)


def _init_firewall() -> None:
    """Initialize firewall rules and apply whitelist."""
    client = _get_client()
    container = _get_container(client, FIREWALL_SERVICE)
    if not container:
        return

    container.exec_run("/usr/local/bin/firewall-init.sh", privileged=True)

    whitelist_src = PROJECT_ROOT / "docker" / "firewall" / "whitelist.txt"
    if whitelist_src.exists():
        data = whitelist_src.read_bytes()
        container.put_archive("/etc/firewall", _tar_single_file("whitelist.txt", data))
        container.exec_run("/usr/local/bin/firewall-apply.sh", privileged=True)


def _tar_single_file(name: str, data: bytes) -> bytes:
    """Create a tar archive with a single file (for put_archive)."""
    import io
    import tarfile

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.read()


def stop_containers() -> None:
    """Stop sandbox then firewall."""
    env = _compose_env()
    base = _compose_cmd()
    subprocess.run([*base, "stop", SANDBOX_SERVICE], env=env, check=False)
    subprocess.run([*base, "stop", FIREWALL_SERVICE], env=env, check=False)


def rebuild_containers() -> None:
    """Rebuild images and restart."""
    env = _compose_env()
    base = _compose_cmd()
    stop_containers()
    subprocess.run([*base, "build"], env=env, check=True)
    start_containers(build=True)


def attach_to_sandbox() -> None:
    """Attach to sandbox container with an interactive shell."""
    env = _compose_env()
    base = _compose_cmd()
    os.execvpe(
        base[0],
        [*base, "exec", SANDBOX_SERVICE, "bash", "-l"],
        env,
    )


def get_status() -> dict[str, dict[str, str]]:
    """Get status of all sandbox containers."""
    client = _get_client()
    result = {}

    for service in [FIREWALL_SERVICE, SANDBOX_SERVICE]:
        container = _get_container(client, service)
        if container:
            result[service] = {
                "status": container.status,
                "id": container.short_id,
                "image": container.image.tags[0] if container.image.tags else "unknown",
            }
        else:
            result[service] = {"status": "not found", "id": "-", "image": "-"}

    return result


def exec_in_sandbox(command: list[str]) -> tuple[int, str]:
    """Execute command in sandbox container, return (exit_code, output)."""
    client = _get_client()
    container = _get_container(client, SANDBOX_SERVICE)
    if not container or container.status != "running":
        return 1, "Sandbox container is not running"

    result = container.exec_run(command)
    return result.exit_code, result.output.decode()


def exec_in_firewall(command: list[str]) -> tuple[int, str]:
    """Execute command in firewall container, return (exit_code, output)."""
    client = _get_client()
    container = _get_container(client, FIREWALL_SERVICE)
    if not container or container.status != "running":
        return 1, "Firewall container is not running"

    result = container.exec_run(command, privileged=True)
    return result.exit_code, result.output.decode()
