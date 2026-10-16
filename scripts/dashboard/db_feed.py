"""Database change feed for one instance.

Two sources, because neither is complete alone:
  * pg_stat_user_tables counters — every insert/update/delete on every table,
    hard deletes included, but no row detail.
  * Plane's audit columns (created_at/updated_at/deleted_at/updated_by_id) —
    which row changed, how, and who did it. Only queried for tables whose
    counters moved since the last poll, so a quiet database costs one query.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass

from instances import Instance

LABEL_COLUMNS = ("name", "title", "display_name", "email", "identifier", "key", "slug")
NOISY_PREFIXES = (
    "django_celery_beat",
    "django_session",
    "user_recent_visits",
    "project_github_syncs",
)
SEP = "\x1f"


@dataclass
class RowChange:
    ts: str
    table: str
    op: str  # create | update | delete
    row_id: str
    label: str
    actor: str


@dataclass
class TableDelta:
    table: str
    ins: int
    upd: int
    dele: int


def local_time(epoch: str) -> str:
    return time.strftime("%m-%d %H:%M:%S", time.localtime(float(epoch)))


def is_noisy(table: str) -> bool:
    return table.startswith(NOISY_PREFIXES)


class ChangeFeed:
    def __init__(self, inst: Instance):
        self.inst = inst
        self.audit: dict[str, tuple[str | None, bool, bool]] = {}
        self.counters: dict[str, tuple[int, int, int]] = {}
        self.since = ""
        self.seen: dict[tuple[str, str, str], None] = {}

    def _query(self, sql: str) -> list[list[str]]:
        out = subprocess.run(
            self.inst.psql(sql), capture_output=True, text=True, timeout=30, check=False
        )
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip())
        return [line.split(SEP) for line in out.stdout.splitlines() if line]

    def load_schema(self) -> None:
        rows = self._query(
            "SELECT table_name, string_agg(column_name, ',') FROM information_schema.columns "
            "WHERE table_schema='public' GROUP BY table_name"
        )
        for table, cols in rows:
            names = set(cols.split(","))
            if {"id", "created_at", "updated_at"} <= names:
                label = next((c for c in LABEL_COLUMNS if c in names), None)
                self.audit[table] = (
                    label,
                    "deleted_at" in names,
                    "updated_by_id" in names,
                )

    def _row_sql(self, table: str, since: str, limit: int) -> str:
        label, soft, by = self.audit[table]
        label_expr = (
            f"left(regexp_replace(t.\"{label}\"::text, '\\s+', ' ', 'g'), 80)"
            if label
            else "''"
        )
        deleted = (
            "t.deleted_at IS NOT NULL AND t.deleted_at >= t.updated_at - interval '2 seconds'"
            if soft
            else "false"
        )
        actor = "coalesce(u.email, '')" if by else "''"
        join = "LEFT JOIN users u ON u.id = t.updated_by_id" if by else ""
        return (
            f"(SELECT extract(epoch FROM t.updated_at)::text, '{table}', "
            f"CASE WHEN {deleted} THEN 'delete' "
            f"WHEN t.updated_at - t.created_at < interval '1 second' THEN 'create' ELSE 'update' END, "
            f"t.id::text, coalesce({label_expr}, ''), {actor}, t.updated_at "
            f'FROM "{table}" t {join} WHERE t.updated_at > {since} '
            f"ORDER BY t.updated_at DESC LIMIT {limit})"
        )

    def _rows(
        self, tables: list[str], since: str, per_table: int, total: int
    ) -> list[RowChange]:
        if not tables:
            return []
        union = " UNION ALL ".join(self._row_sql(t, since, per_table) for t in tables)
        sql = f"SELECT * FROM (SELECT * FROM ({union}) x ORDER BY 7 DESC LIMIT {total}) y ORDER BY 7"
        fresh = []
        for r in self._query(sql):
            key = (r[1], r[3], r[6])
            if key not in self.seen:
                self.seen[key] = None
                fresh.append(RowChange(local_time(r[0]), *r[1:6]))
        while len(self.seen) > 5000:  # dicts keep insertion order: drop oldest
            del self.seen[next(iter(self.seen))]
        return fresh

    def _stats(self) -> list[TableDelta]:
        rows = self._query(
            "SELECT now(), relname, n_tup_ins, n_tup_upd, n_tup_del FROM pg_stat_user_tables"
        )
        first = not self.counters
        deltas = []
        for now, table, *nums in rows:
            self.since = now
            cur = tuple(int(n) for n in nums)
            prev = self.counters.get(table)
            self.counters[table] = cur
            if first or prev is None or prev == cur:
                continue
            d = [c - p for c, p in zip(cur, prev)]
            if min(d) < 0:  # stats were reset (db restart); start over from here
                continue
            deltas.append(TableDelta(table, *d))
        return deltas

    def backfill(self, limit: int = 150) -> list[RowChange]:
        """Most recent changes across every audited table, oldest first."""
        self.load_schema()
        self._stats()
        return self._rows(sorted(self.audit), "'-infinity'::timestamptz", 25, limit)

    def poll(self) -> tuple[list[TableDelta], list[RowChange]]:
        since = self.since
        deltas = self._stats()
        changed = [d.table for d in deltas if d.table in self.audit]
        # Overlap the window: updated_at is stamped before commit, so a row can
        # land with a timestamp just behind the previous poll's now().
        window = f"'{since}'::timestamptz - interval '10 seconds'"
        return deltas, self._rows(changed, window, 50, 300)
