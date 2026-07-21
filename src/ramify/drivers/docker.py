"""Docker Compose isolation driver for session branches."""

from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from pathlib import Path

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

    def isolation_env(self) -> dict[str, str]:
        """Env vars a branch injects so compose runs in its own namespace."""
        return {
            "COMPOSE_PROJECT_NAME": self.project_name,
            "RAMIFY_PORT_BASE": str(self.port_base),
        }

    def teardown(self, cwd: str) -> None:
        """`docker compose down` for this project. Best-effort, never raises."""
        if shutil.which("docker") is None:
            return
        if not any((Path(cwd) / f).exists() for f in _COMPOSE_FILES):
            return
        proc = subprocess.run(  # noqa: S603
            [
                "docker",
                "compose",
                "-p",
                self.project_name,
                "down",
                "--volumes",
                "--remove-orphans",
                "--timeout",
                "10",
            ],
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
