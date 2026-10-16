"""Server-wide operations, run detached so closing the dashboard can't kill one.

Each run is a `bash` process in its own session writing to a log file. A
per-instance lockfile (removed by the script itself on exit) makes runs
exclusive and lets a restarted dashboard reattach to one still in flight.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from instances import (
    APP_SERVICES,
    BACKUP_DIR,
    BUILD_SERVICES,
    ROOT,
    STATE_DIR,
    Instance,
)

OPS_DIR = STATE_DIR / "ops"
_children: dict[
    int, subprocess.Popen
] = {}  # our own runs; kill(pid, 0) sees zombies as alive


@dataclass(frozen=True)
class Op:
    key: str
    label: str
    summary: str
    variant: str  # textual Button variant


OPS = [
    Op(
        "restart",
        "Restart",
        "Restart every app service (datastores stay up).",
        "warning",
    ),
    Op(
        "update",
        "Update",
        "Back up the DB, rebuild all images from the checkout, migrate, recreate.",
        "primary",
    ),
    Op(
        "migrate",
        "Migrate",
        "Run pending Django migrations with the migrator image.",
        "default",
    ),
    Op("backup", "Backup DB", f"pg_dump the database to {BACKUP_DIR}.", "success"),
    Op(
        "stop",
        "Stop",
        "Stop every app service; the site goes down, data is kept.",
        "error",
    ),
    Op("start", "Start", "docker compose up -d for the whole stack.", "success"),
]
OPS_BY_KEY = {op.key: op for op in OPS}


def _script(inst: Instance, op: str) -> list[str]:
    dc, apps = inst.compose, " ".join(APP_SERVICES)
    dump = BACKUP_DIR / f"{inst.key}-$(date +%Y%m%d-%H%M%S).sql.gz"
    head = inst.psql(
        "SELECT name FROM django_migrations WHERE app='db' ORDER BY id DESC LIMIT 1"
    )
    show_head = 'echo "migration head: $(' + shlex.join(head) + ')"'
    backup = [
        f"mkdir -p {BACKUP_DIR}",
        f"docker exec {inst.db_container} pg_dump -U plane plane | gzip > {dump}",
        f"ls -lh {BACKUP_DIR} | tail -1",
    ]
    return {
        "restart": [f"{dc} restart {apps}"],
        "stop": [f"{dc} stop {apps}"],
        "start": [f"{dc} up -d"],
        "backup": backup,
        "migrate": [f"{dc} run --rm migrator", show_head],
        # Every backend image, migrator included: a stale one migrates or runs old code silently.
        "update": backup
        + [
            f"git -C {ROOT} log -1 --format='building %h %s'",
            f"{dc} build {' '.join(BUILD_SERVICES)}",
            f"{dc} run --rm migrator",
            f"{dc} up -d",
            show_head,
        ],
    }[op]


@dataclass
class Run:
    op: str
    log: Path
    pid: int
    started: str


def _lock(inst: Instance) -> Path:
    return OPS_DIR / f"{inst.key}.lock"


def current(inst: Instance) -> Run | None:
    """The run in flight for this instance, if any."""
    try:
        run = Run(**json.loads(_lock(inst).read_text()))
        run.log = Path(run.log)
        child = _children.get(run.pid)
        if child is not None and child.poll() is not None:
            raise ProcessLookupError
        os.kill(run.pid, 0)
        return run
    except (FileNotFoundError, ProcessLookupError, ValueError, TypeError):
        _lock(inst).unlink(missing_ok=True)
        return None


def latest_log(inst: Instance) -> Path | None:
    logs = sorted(OPS_DIR.glob(f"{inst.key}-*.log"))
    return logs[-1] if logs else None


def start(inst: Instance, op: str) -> Run:
    if current(inst):
        raise RuntimeError("another operation is already running on this instance")
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log, lock = OPS_DIR / f"{inst.key}-{stamp}-{op}.log", _lock(inst)
    steps = "\n".join(f'echo "\\$ "{shlex.quote(s)}\n{s}' for s in _script(inst, op))
    body = (
        f"trap 'rc=$?; echo; echo \"── {op} finished: exit $rc at $(date +%T)\"; rm -f {lock}' EXIT\n"
        f'echo "── {op} on {inst.title} ({inst.project}) started $(date)"\n'
        f"set -eo pipefail\ncd {shlex.quote(str(ROOT))}\n{steps}\n"
    )
    with open(log, "w") as fh:
        proc = subprocess.Popen(
            ["bash", "-c", body],
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    _children[proc.pid] = proc
    run = Run(op=op, log=log, pid=proc.pid, started=stamp)
    lock.write_text(json.dumps({**run.__dict__, "log": str(log)}))
    return run
