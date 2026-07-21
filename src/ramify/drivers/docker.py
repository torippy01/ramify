"""Docker Compose isolation driver for session branches."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_COMPOSE_FILES = ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")

# Deterministic per-branch port spacing so parallel branches never collide.
_PORT_SPACING = 100
_PORT_BASE = 20000


class DockerDriver:
    """Assigns an isolated ``COMPOSE_PROJECT_NAME`` and port offset per branch,
    and tears the whole project down deterministically on branch close."""

    def __init__(self, branch_name: str) -> None:
        self.project_name = f"ramify-{branch_name}-{uuid.uuid4().hex[:8]}"
        # Stable offset derived from the unique project name.
        offset = (hash(self.project_name) % 100) * _PORT_SPACING
        self.port_base = _PORT_BASE + offset
        self._temporary_dir = Path(tempfile.mkdtemp(prefix="ramify-compose-"))
        self._resolved_compose: Path | None = None

    def isolation_env(self) -> dict[str, str]:
        """Env vars a branch injects so compose runs in its own namespace."""
        return {
            "COMPOSE_PROJECT_NAME": self.project_name,
            "RAMIFY_PORT_BASE": str(self.port_base),
        }

    def prepare_compose(self, cwd: str, env: dict[str, str]) -> str | None:
        """Resolve Compose config and randomize published host ports.

        Compose's project name isolates container/network names but does not
        isolate fixed host ports. The resolved config is copied to a temporary
        JSON file with every published port set to ``0``; Docker then assigns a
        free host port independently for each branch.

        Returns the temporary config path, or ``None`` when Docker/Compose is
        unavailable or the project cannot be resolved.
        """
        if self._resolved_compose is not None:
            return str(self._resolved_compose)
        if shutil.which("docker") is None:
            return None
        if not any((Path(cwd) / name).exists() for name in _COMPOSE_FILES):
            return None

        compose_env = dict(env)
        compose_env.pop("COMPOSE_FILE", None)
        proc = subprocess.run(  # noqa: S603
            ["docker", "compose", "-p", self.project_name, "config", "--format", "json"],
            cwd=cwd,
            env=compose_env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.warning("docker compose config failed: %s", proc.stderr.strip())
            return None
        try:
            config = json.loads(proc.stdout)
        except json.JSONDecodeError:
            logger.warning("docker compose config returned invalid JSON")
            return None
        self._randomize_published_ports(config)
        resolved = self._temporary_dir / "compose-resolved.json"
        resolved.write_text(json.dumps(config), encoding="utf-8")
        self._resolved_compose = resolved
        return str(resolved)

    @staticmethod
    def _randomize_published_ports(config: dict[str, Any]) -> None:
        services = config.get("services", {})
        if not isinstance(services, dict):
            return
        for service in services.values():
            if not isinstance(service, dict):
                continue
            ports = service.get("ports", [])
            if not isinstance(ports, list):
                continue
            for port in ports:
                if isinstance(port, dict) and port.get("published") is not None:
                    port["published"] = 0

    def teardown(self, cwd: str) -> None:
        """`docker compose down` for this project. Best-effort, never raises."""
        if shutil.which("docker") is None:
            shutil.rmtree(self._temporary_dir, ignore_errors=True)
            return
        if self._resolved_compose is None and not any(
            (Path(cwd) / f).exists() for f in _COMPOSE_FILES
        ):
            shutil.rmtree(self._temporary_dir, ignore_errors=True)
            return
        command = ["docker", "compose", "-p", self.project_name]
        if self._resolved_compose is not None:
            command.extend(["-f", str(self._resolved_compose)])
        command.extend(["down", "--volumes", "--remove-orphans", "--timeout", "10"])
        proc = subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            logger.warning(
                "docker compose down failed for %s: %s", self.project_name, proc.stderr.strip()
            )
        else:
            logger.info("tore down docker project %s", self.project_name)
        shutil.rmtree(self._temporary_dir, ignore_errors=True)
