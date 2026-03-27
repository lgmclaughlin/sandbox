"""Docker container management via Docker SDK."""

import os
import subprocess
import sys
from pathlib import Path

import docker
from docker.errors import DockerException, NotFound

from cli.lib.config import PROJECT_ROOT, load_env, get_active_project_name, DEFAULT_LOG_DIR

import yaml

COMPOSE_FILE = PROJECT_ROOT / "docker" / "docker-compose.yml"
COMPOSE_OVERRIDE_FILE = PROJECT_ROOT / "docker" / "docker-compose.override.yml"
FIREWALL_SERVICE = "firewall"
PROXY_SERVICE = "proxy"
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


def _is_proxy_mode() -> bool:
    env = load_env()
    return env.get("SANDBOX_PROXY_MODE", "firewall-only") == "proxy"


def _compose_cmd() -> list[str]:
    env = load_env()
    project = env.get("COMPOSE_PROJECT_NAME", "project")
    cmd = [
        "docker", "compose",
        "-p", project,
        "-f", str(COMPOSE_FILE),
    ]
    if COMPOSE_OVERRIDE_FILE.exists():
        cmd.extend(["-f", str(COMPOSE_OVERRIDE_FILE)])
    if _is_proxy_mode():
        cmd.extend(["--profile", "proxy"])
    return cmd


def _generate_override() -> None:
    """Generate docker-compose.override.yml for conditional features."""
    env = load_env()
    override: dict = {"services": {}}
    has_overrides = False

    cpu_limit = env.get("SANDBOX_CPU_LIMIT", "")
    mem_limit = env.get("SANDBOX_MEM_LIMIT", "")
    if cpu_limit or mem_limit:
        limits: dict = {}
        if cpu_limit:
            limits["cpus"] = cpu_limit
        if mem_limit:
            limits["memory"] = mem_limit
        override["services"]["sandbox"] = {
            "deploy": {"resources": {"limits": limits}}
        }
        has_overrides = True

    hardened = env.get("SANDBOX_HARDENED_MODE", "").lower() == "true"
    if hardened:
        sandbox = override["services"].setdefault("sandbox", {})
        sandbox["read_only"] = True
        sandbox.setdefault("tmpfs", []).extend([
            "/tmp:size=256m",
            "/run:size=64m",
            "/home/node:size=512m",
        ])
        sandbox["cap_drop"] = ["ALL"]
        has_overrides = True

    proxy_mode = env.get("SANDBOX_PROXY_MODE", "firewall-only") == "proxy"
    if proxy_mode:
        sandbox = override["services"].setdefault("sandbox", {})
        sandbox_env = sandbox.setdefault("environment", [])
        sandbox_env.extend([
            "HTTP_PROXY=http://localhost:8080",
            "HTTPS_PROXY=http://localhost:8080",
        ])
        sandbox.setdefault("volumes", []).append(
            "proxy_certs:/usr/local/share/ca-certificates/proxy:ro"
        )
        has_overrides = True

        inspection_file = PROJECT_ROOT / "config" / "network" / "inspection.yaml"
        if inspection_file.exists():
            proxy = override["services"].setdefault("proxy", {})
            proxy.setdefault("volumes", []).append(
                f"{inspection_file}:/etc/proxy/inspection.yaml:ro"
            )

    if has_overrides:
        COMPOSE_OVERRIDE_FILE.write_text(yaml.dump(override, default_flow_style=False))
    elif COMPOSE_OVERRIDE_FILE.exists():
        COMPOSE_OVERRIDE_FILE.unlink()


def _workspace_dir() -> Path:
    """Get the workspace directory.

    Resolution order:
    1. SANDBOX_WORKSPACE_DIR env var (set by CLI or project .env)
    2. Project-specific workspace directory
    3. Root-level workspace/
    """
    from_env = os.environ.get("SANDBOX_WORKSPACE_DIR", "")
    if from_env:
        return Path(from_env).resolve()

    env = load_env()
    from_config = env.get("SANDBOX_WORKSPACE_DIR", "")
    if from_config:
        path = Path(from_config)
        return path if path.is_absolute() else PROJECT_ROOT / path

    project = get_active_project_name()
    if project:
        return PROJECT_ROOT / "projects" / project / "workspace"
    return PROJECT_ROOT / "workspace"


def _compose_env() -> dict[str, str]:
    """Build environment for docker compose commands."""
    from cli.lib.config import DEFAULT_LOG_DIR
    env = {**os.environ, **load_env()}
    env["SANDBOX_WORKSPACE_DIR"] = str(_workspace_dir())
    env["SANDBOX_LOG_DIR"] = str(DEFAULT_LOG_DIR)
    try:
        env.setdefault("USER_ID", str(os.getuid()))
        env.setdefault("GROUP_ID", str(os.getgid()))
    except AttributeError:
        env.setdefault("USER_ID", "1000")
        env.setdefault("GROUP_ID", "1000")
    return env


def is_running(service: str) -> bool:
    client = _get_client()
    container = _get_container(client, service)
    return container is not None and container.status == "running"


def start_containers(build: bool = False, secrets: dict[str, str] | None = None, offline: bool = False) -> None:
    """Start firewall and sandbox containers."""
    _generate_override()

    env = _compose_env()

    if secrets:
        env.update(secrets)

    base = _compose_cmd()

    proxy_mode = _is_proxy_mode()

    if not is_running(FIREWALL_SERVICE):
        subprocess.run([*base, "up", "-d", FIREWALL_SERVICE], env=env, check=True)

    if build or not is_running(FIREWALL_SERVICE):
        _init_firewall(offline=offline)

    if proxy_mode and not is_running(PROXY_SERVICE):
        subprocess.run([*base, "up", "-d", PROXY_SERVICE], env=env, check=True)
        _inject_proxy_ca()

    if build:
        subprocess.run([*base, "build", SANDBOX_SERVICE], env=env, check=True)

    subprocess.run([*base, "up", "-d", SANDBOX_SERVICE], env=env, check=True)

    if proxy_mode and is_running(SANDBOX_SERVICE):
        _update_sandbox_ca()


def _init_firewall(offline: bool = False) -> None:
    """Initialize firewall rules and apply whitelist."""
    client = _get_client()
    container = _get_container(client, FIREWALL_SERVICE)
    if not container:
        return

    if offline:
        container.exec_run(
            ["bash", "-c", "SANDBOX_OFFLINE_MODE=true /usr/local/bin/firewall-init.sh"],
            privileged=True,
        )
    else:
        container.exec_run("/usr/local/bin/firewall-init.sh", privileged=True)

    whitelist_src = PROJECT_ROOT / "docker" / "firewall" / "whitelist.txt"
    if whitelist_src.exists():
        data = whitelist_src.read_bytes()
        container.put_archive("/etc/firewall", _tar_single_file("whitelist.txt", data))
        if not offline:
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


def _inject_proxy_ca() -> None:
    """Copy custom CA cert into the proxy if configured."""
    env = load_env()
    custom_ca = env.get("SANDBOX_PROXY_CA_CERT", "")
    if not custom_ca:
        return

    ca_path = Path(custom_ca)
    if not ca_path.exists():
        return

    client = _get_client()
    container = _get_container(client, PROXY_SERVICE)
    if not container:
        return

    data = ca_path.read_bytes()
    container.put_archive(
        "/home/mitmproxy/.mitmproxy",
        _tar_single_file("mitmproxy-ca-cert.pem", data),
    )


def _update_sandbox_ca() -> None:
    """Update CA certificates in the sandbox container for proxy trust."""
    client = _get_client()
    container = _get_container(client, SANDBOX_SERVICE)
    if not container:
        return

    container.exec_run(
        ["bash", "-c", "update-ca-certificates 2>/dev/null || true"],
        user="root",
    )


def stop_containers() -> None:
    """Stop sandbox, proxy (if running), then firewall."""
    env = _compose_env()
    base = _compose_cmd()
    subprocess.run([*base, "stop", SANDBOX_SERVICE], env=env, check=False)
    if is_running(PROXY_SERVICE):
        subprocess.run([*base, "stop", PROXY_SERVICE], env=env, check=False)
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
    cmd = [*base, "exec", SANDBOX_SERVICE, "bash", "-l"]

    if hasattr(os, "execvpe"):
        os.execvpe(base[0], cmd, env)
    else:
        # Windows: no execvpe, use subprocess and forward exit code
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)


def get_status() -> dict[str, dict[str, str]]:
    """Get status of all sandbox containers."""
    client = _get_client()
    result = {}

    services = [FIREWALL_SERVICE, SANDBOX_SERVICE]
    if _is_proxy_mode():
        services.insert(1, PROXY_SERVICE)

    for service in services:
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
