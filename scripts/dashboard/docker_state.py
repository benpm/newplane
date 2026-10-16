"""Point-in-time snapshot of one instance: containers, images, HTTP, schema."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from instances import BACKEND_IMAGES, ROOT, Instance


@dataclass
class Container:
    name: str
    service: str
    state: str
    health: str
    started: datetime | None
    image_built: datetime | None
    restarts: int
    outdated: bool  # its image tag was rebuilt since the container was created


@dataclass
class Snapshot:
    containers: list[Container] = field(default_factory=list)
    http: str = "?"
    migration: str = "?"
    stale_backend: bool = False
    error: str = ""


def run(cmd: list[str], timeout: float = 15) -> str:
    out = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"{cmd[0]} exited {out.returncode}")
    return out.stdout


def parse_ts(value: str) -> datetime | None:
    if not value or value.startswith("0001"):
        return None
    # Docker emits nanoseconds; fromisoformat only takes microseconds.
    head, _, frac = value.rstrip("Z").partition(".")
    return datetime.fromisoformat(f"{head}.{(frac + '000000')[:6]}+00:00")


def images() -> tuple[dict[str, datetime | None], dict[str, str]]:
    """(image id -> build time, repo:tag -> image id). Tolerates deleted images."""
    built, tags = {}, {}
    fmt = "{{.ID}}|{{.Repository}}:{{.Tag}}|{{.CreatedAt}}"
    for line in run(
        ["docker", "images", "-a", "--no-trunc", "--format", fmt]
    ).splitlines():
        image_id, tag, created = line.split("|", 2)
        built[image_id] = datetime.strptime(created[:25], "%Y-%m-%d %H:%M:%S %z")
        tags[tag] = image_id
    return built, tags


def containers(inst: Instance) -> list[Container]:
    ids = run(
        [
            "docker",
            "ps",
            "-aq",
            "--filter",
            f"label=com.docker.compose.project={inst.project}",
        ]
    ).split()
    if not ids:
        return []
    built, tags = images()
    result = []
    for c in json.loads(run(["docker", "inspect", *ids])):
        st = c["State"]
        ref = c["Config"]["Image"]
        tag_id = tags.get(ref if ":" in ref else f"{ref}:latest")
        result.append(
            Container(
                name=c["Name"].lstrip("/"),
                service=c["Config"]["Labels"].get("com.docker.compose.service", "?"),
                state=st["Status"],
                health=st.get("Health", {}).get("Status", "-"),
                started=parse_ts(st["StartedAt"]) if st["Running"] else None,
                image_built=built.get(c["Image"]),
                restarts=c.get("RestartCount", 0),
                outdated=tag_id is not None and tag_id != c["Image"],
            )
        )
    return sorted(result, key=lambda c: c.service)


def http_status(port: int) -> str:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=4) as resp:
            return str(resp.status)
    except urllib.error.HTTPError as e:
        return str(e.code)
    except OSError as e:
        return f"down ({getattr(e, 'reason', e)})"


def migration_head(inst: Instance) -> str:
    sql = "SELECT name FROM django_migrations WHERE app='db' ORDER BY id DESC LIMIT 1"
    return run(inst.psql(sql)).strip() or "none"


def snapshot(inst: Instance) -> Snapshot:
    snap = Snapshot(http=http_status(inst.port))
    try:
        snap.containers = containers(inst)
        backend = {
            c.image_built
            for c in snap.containers
            if c.service in BACKEND_IMAGES and c.image_built
        }
        # Separate images per backend service: one built at a different time means
        # a partial rebuild, and new Celery tasks get silently discarded.
        snap.stale_backend = (
            max(backend) - min(backend) > timedelta(minutes=10)
            if len(backend) > 1
            else False
        )
        snap.migration = migration_head(inst)
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        snap.error = str(e)
    return snap


def git_summary() -> str:
    try:
        head = run(["git", "-C", str(ROOT), "log", "-1", "--format=%h %s"]).strip()
        branch = run(["git", "-C", str(ROOT), "branch", "--show-current"]).strip()
        dirty = len(run(["git", "-C", str(ROOT), "status", "--porcelain"]).splitlines())
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        return f"git: {e}"
    return f"{branch} @ {head[:60]}" + (f"  (+{dirty} uncommitted)" if dirty else "")


def ago(ts: datetime | None) -> str:
    if ts is None:
        return "-"
    secs = int((datetime.now(timezone.utc) - ts).total_seconds())
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= size:
            return f"{secs // size}{unit}"
    return f"{secs}s"
