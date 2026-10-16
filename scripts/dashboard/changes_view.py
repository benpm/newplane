"""Widgets for the database change feed: a filterable row log and a per-table tally."""

from __future__ import annotations

import time
from collections import deque

from db_feed import RowChange, TableDelta, is_noisy
from instances import STATE_DIR
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Input, RichLog

OP_STYLE = {"create": ("+", "green"), "update": ("~", "yellow"), "delete": ("-", "red")}


class ChangeLog(Vertical):
    """Chronological row changes. Also appended to a plain-text file per instance."""

    def __init__(self, key: str, **kw):
        super().__init__(**kw)
        self.entries: deque[RowChange] = deque(maxlen=5000)
        self.show_noise = False
        self.path = STATE_DIR / "changes" / f"{key}.log"

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="filter by table, label or user…  (n toggles noisy tables)"
        )
        yield RichLog(max_lines=5000, wrap=False, auto_scroll=True)

    def _visible(self, c: RowChange) -> bool:
        if not self.show_noise and is_noisy(c.table):
            return False
        needle = self.query_one(Input).value.lower()
        return not needle or needle in f"{c.table} {c.label} {c.actor} {c.op}".lower()

    def _line(self, c: RowChange) -> Text:
        sign, style = OP_STYLE.get(c.op, ("?", "white"))
        line = Text(f"{c.ts} ", style="dim")
        line.append(f"{sign} {c.op:<6} ", style=f"bold {style}")
        line.append(f"{c.table:<28} ", style="cyan")
        line.append(c.label or c.row_id[:8], style="bold" if c.label else "dim")
        if c.actor:
            line.append(f"  by {c.actor}", style="magenta")
        return line

    def add(self, changes: list[RowChange], persist: bool = True) -> None:
        log = self.query_one(RichLog)
        for c in changes:
            self.entries.append(c)
            if self._visible(c):
                log.write(self._line(c))
        if persist and changes:
            self._persist(
                f"{c.ts}\t{c.op}\t{c.table}\t{c.row_id}\t{c.label}\t{c.actor}"
                for c in changes
            )

    def add_hard_deletes(self, deltas: list[TableDelta]) -> None:
        """Rows that vanished outright; only the counters can see these."""
        stamp = time.strftime("%m-%d %H:%M:%S")
        for d in deltas:
            if d.dele and (self.show_noise or not is_noisy(d.table)):
                self.query_one(RichLog).write(
                    Text(f"{stamp} ", style="dim")
                    + Text(
                        f"✗ {d.dele} row(s) deleted from {d.table}", style="bold red"
                    )
                )
                self._persist([f"{stamp}\thard-delete\t{d.table}\t{d.dele}"])

    def _persist(self, lines) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as fh:
            fh.writelines(f"{line}\n" for line in lines)

    def rerender(self) -> None:
        log = self.query_one(RichLog)
        log.clear()
        for c in self.entries:
            if self._visible(c):
                log.write(self._line(c))

    def on_input_changed(self, _event: Input.Changed) -> None:
        self.rerender()


class TableActivity(DataTable):
    """Insert/update/delete counts per table since the dashboard started."""

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.add_columns("table", "inserts", "updates", "deletes", "last change")
        self.totals: dict[str, list] = {}

    def add(self, deltas: list[TableDelta]) -> None:
        if not deltas:
            return
        now = time.strftime("%H:%M:%S")
        for d in deltas:
            t = self.totals.setdefault(d.table, [0, 0, 0, ""])
            t[0] += d.ins
            t[1] += d.upd
            t[2] += d.dele
            t[3] = now
        self.clear()
        for table, (i, u, x, last) in sorted(
            self.totals.items(), key=lambda kv: kv[1][3], reverse=True
        ):
            self.add_row(
                Text(table, style="dim" if is_noisy(table) else "cyan"),
                Text(f"+{i}", style="green"),
                Text(f"~{u}", style="yellow"),
                Text(f"-{x}", style="red"),
                last,
            )
