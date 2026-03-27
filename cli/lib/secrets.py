"""Secrets management with pluggable providers."""

import base64
import hashlib
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from cli.lib.config import PROJECT_ROOT, load_env


SECRETS_DIR = PROJECT_ROOT / ".secrets"


class SecretsProvider(ABC):
    """Base class for secrets providers."""

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieve a secret by key."""

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        """Store a secret."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a secret. Returns True if it existed."""

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all stored secret keys (not values)."""


class LocalProvider(SecretsProvider):
    """Stores secrets in an obfuscated local file.

    Uses base64 encoding with a machine-specific key. This is not
    cryptographically secure storage, but prevents accidental exposure
    of plaintext secrets in the project directory. For production
    security, use Vault or AWS Secrets Manager providers.
    """

    def __init__(self, path: Path | None = None):
        self.path = path or SECRETS_DIR / "local.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _machine_key(self) -> bytes:
        """Derive a machine-specific key for obfuscation."""
        import getpass
        import socket
        seed = f"{getpass.getuser()}@{socket.gethostname()}"
        return hashlib.sha256(seed.encode()).digest()

    def _encode(self, value: str) -> str:
        key = self._machine_key()
        encoded = bytes(a ^ b for a, b in zip(value.encode(), key * (len(value) // len(key) + 1)))
        return base64.b64encode(encoded).decode()

    def _decode(self, encoded: str) -> str:
        key = self._machine_key()
        decoded = base64.b64decode(encoded)
        return bytes(a ^ b for a, b in zip(decoded, key * (len(decoded) // len(key) + 1))).decode()

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2) + "\n")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass  # Windows: NTFS permissions handled differently

    def get(self, key: str) -> str | None:
        encoded = self._data.get(key)
        if encoded is None:
            return None
        return self._decode(encoded)

    def set(self, key: str, value: str) -> None:
        self._data[key] = self._encode(value)
        self._save()

    def delete(self, key: str) -> bool:
        if key not in self._data:
            return False
        del self._data[key]
        self._save()
        return True

    def list_keys(self) -> list[str]:
        return sorted(self._data.keys())


class EnvProvider(SecretsProvider):
    """Reads secrets from environment variables. Read-only, for CI use."""

    def get(self, key: str) -> str | None:
        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:
        raise RuntimeError("EnvProvider is read-only. Set secrets as environment variables.")

    def delete(self, key: str) -> bool:
        raise RuntimeError("EnvProvider is read-only.")

    def list_keys(self) -> list[str]:
        return []


def get_provider(provider_name: str | None = None) -> SecretsProvider:
    """Get the configured secrets provider."""
    if provider_name is None:
        env = load_env()
        provider_name = env.get("SANDBOX_SECRETS_PROVIDER", "local")

    providers = {
        "local": LocalProvider,
        "env": EnvProvider,
    }

    provider_cls = providers.get(provider_name)
    if not provider_cls:
        raise ValueError(f"Unknown secrets provider: {provider_name}. Available: {', '.join(providers)}")

    return provider_cls()


def get_secrets_for_container() -> dict[str, str]:
    """Collect all secrets that should be injected into the container."""
    provider = get_provider()
    secrets = {}
    for key in provider.list_keys():
        value = provider.get(key)
        if value is not None:
            secrets[key] = value
    return secrets


def mask_value(value: str) -> str:
    """Mask a secret value for display."""
    if len(value) <= 4:
        return "****"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
