"""The Plane deployments this dashboard knows about, and how to drive each one."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path

# The checkout production builds from. Its uncommitted .env and
# docker-compose.override.yml are load-bearing, so a worktree is the wrong root.
ROOT = Path(os.environ.get("PLANE_ROOT", "/home/beb/live/plane"))
DEV_ENV_DIR = Path("/home/beb/live/plane-dev-env")
STATE_DIR = (
    Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "plane-dash"
)
BACKUP_DIR = Path.home() / "plane-backups"

APP_SERVICES = [
    "api",
    "worker",
    "beat-worker",
    "web",
    "admin",
    "space",
    "live",
    "proxy",
]
# migrator is a fourth image off Dockerfile.api: skip it and migrate runs stale code.
BACKEND_IMAGES = ["api", "worker", "beat-worker", "migrator"]
BUILD_SERVICES = BACKEND_IMAGES + ["web", "admin", "space", "live"]


@dataclass(frozen=True)
class Instance:
    key: str
    title: str
    project: str
    url: str
    port: int
    db_container: str
    compose_args: list[str] = field(default_factory=list)

    @property
    def compose(self) -> str:
        """A shell prefix for `docker compose` bound to this project."""
        return " ".join(["docker", "compose", *map(shlex.quote, self.compose_args)])

    def psql(self, sql: str) -> list[str]:
        return [
            "docker",
            "exec",
            self.db_container,
            "psql",
            "-U",
            "plane",
            "-d",
            "plane",
            "-AtX",
            "-F",
            "\x1f",
            "-c",
            sql,
        ]


INSTANCES = [
    Instance(
        key="prod",
        title="production",
        project="plane",
        url="https://plane.mousetrip.online",
        port=8090,
        db_container="plane-db",
        # No -f: compose then also loads the local docker-compose.override.yml.
        compose_args=["--project-name", "plane", "--project-directory", str(ROOT)],
    ),
    Instance(
        key="dev",
        title="dev site",
        project="planedev",
        url="https://dev.mousetrip.online",
        port=8091,
        db_container="plane-db-dev",
        compose_args=[
            "--project-name",
            "planedev",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(DEV_ENV_DIR / "root.env"),
            "-f",
            str(ROOT / "docker-compose.yml"),
            "-f",
            str(ROOT / "docker-compose.devsite.yml"),
        ],
    ),
]
