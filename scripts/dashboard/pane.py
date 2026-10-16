"""Everything shown for one instance: status, ops buttons, containers, DB feed, ops log."""

from __future__ import annotations

import subprocess
from pathlib import Path

import ops
from changes_view import ChangeLog, TableActivity
from db_feed import ChangeFeed
from docker_state import Snapshot, ago, snapshot
from instances import Instance
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, RichLog, Static, TabbedContent, TabPane

STATE_STYLE = {
    "running": "green",
    "exited": "dim",
    "restarting": "yellow",
    "dead": "red",
}
HEALTH_STYLE = {"healthy": "green", "unhealthy": "bold red", "starting": "yellow"}


class InstancePane(Vertical):
    def __init__(self, inst: Instance, **kw):
        super().__init__(**kw)
        self.inst = inst
        self.feed = ChangeFeed(inst)
        self.git = ""
        self.snap = Snapshot()
        self.tail: tuple[Path, int] | None = None
        self.running: ops.Run | None = None

    def compose(self) -> ComposeResult:
        yield Static(classes="info")
        with Horizontal(classes="ops"):
            for op in ops.OPS:
                yield Button(op.label, id=f"op-{op.key}", variant=op.variant)
        yield DataTable(classes="containers", cursor_type="row")
        with TabbedContent(classes="lower"):
            with TabPane("DB changes"):
                yield ChangeLog(self.inst.key)
            with TabPane("Table activity"):
                yield TableActivity()
            with TabPane("Operation log", id=f"oplog-{self.inst.key}"):
                yield RichLog(classes="oplog", max_lines=5000, wrap=True)

    def on_mount(self) -> None:
        self.query_one(".containers", DataTable).add_columns(
            "service", "container", "state", "health", "up", "image built", "notes"
        )
        self.running = ops.current(self.inst)
        log = self.running.log if self.running else ops.latest_log(self.inst)
        if log:
            self.follow(log)
        self.refresh_state()
        self.start_feed()
        self.set_interval(5, self.refresh_state)
        self.set_interval(3, self.poll_feed)
        self.set_interval(0.5, self.tick_ops)

    # ── status ────────────────────────────────────────────────────────────
    @work(thread=True, exclusive=True, group="state")
    def refresh_state(self) -> None:
        snap = snapshot(self.inst)
        self.app.call_from_thread(self.show_state, snap)

    def show_state(self, snap: Snapshot) -> None:
        self.snap = snap
        table = self.query_one(".containers", DataTable)
        table.clear()
        for c in snap.containers:
            notes = []
            if c.outdated and c.service != "migrator":
                notes.append(Text("image rebuilt, not deployed", style="yellow"))
            if c.restarts:
                notes.append(Text(f"{c.restarts} restarts", style="red"))
            table.add_row(
                Text(c.service, style="bold"),
                c.name,
                Text(c.state, style=STATE_STYLE.get(c.state, "red")),
                Text(c.health, style=HEALTH_STYLE.get(c.health, "dim")),
                ago(c.started),
                ago(c.image_built) + (" ago" if c.image_built else ""),
                Text("  ").join(notes),
            )
        self.render_info()

    def render_info(self) -> None:
        s, i = self.snap, self.inst
        ok = s.http.startswith(("2", "3"))
        up = sum(c.state == "running" for c in s.containers)
        t = Text()
        t.append("● " if ok else "✗ ", style="bold green" if ok else "bold red")
        t.append(f"HTTP {s.http}", style="green" if ok else "red")
        t.append(f"  {i.url}  ", style="underline")
        t.append(
            f"localhost:{i.port}  ·  project {i.project}  ·  {up}/{len(s.containers)} running\n",
            style="dim",
        )
        t.append("schema  ", style="dim")
        t.append(f"db.{s.migration}\n", style="cyan")
        t.append("checkout ", style="dim")
        t.append(f"{self.app.git}\n")
        if self.running:
            t.append(
                f"⟳ {self.running.op} running since {self.running.started}",
                style="bold yellow",
            )
        else:
            t.append("idle — no operation running", style="dim")
        if s.stale_backend:
            t.append(
                "\n⚠ api/worker/beat-worker/migrator images were built at different times",
                style="bold yellow",
            )
        if s.error:
            t.append(f"\n✗ {s.error}", style="bold red")
        self.query_one(".info", Static).update(t)

    # ── database feed ─────────────────────────────────────────────────────
    @work(thread=True, exclusive=True, group="feed")
    def start_feed(self) -> None:
        try:
            rows = self.feed.backfill()
        except (
            RuntimeError,
            OSError,
            subprocess.TimeoutExpired,
        ) as e:  # db down: retry on poll
            rows = []
            self.app.call_from_thread(
                self.app.notify, f"{self.inst.title}: {e}", severity="error"
            )
        self.app.call_from_thread(self.query_one(ChangeLog).add, rows, False)

    @work(thread=True, exclusive=True, group="feed")
    def poll_feed(self) -> None:
        try:
            if not self.feed.audit:
                self.feed.load_schema()
            deltas, rows = self.feed.poll()
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            return
        self.app.call_from_thread(self.show_feed, deltas, rows)

    def show_feed(self, deltas, rows) -> None:
        self.query_one(ChangeLog).add(rows)
        self.query_one(ChangeLog).add_hard_deletes(deltas)
        self.query_one(TableActivity).add(deltas)

    # ── operations ────────────────────────────────────────────────────────
    def follow(self, log: Path) -> None:
        self.query_one(".oplog", RichLog).clear()
        self.tail = (log, 0)

    def tick_ops(self) -> None:
        was, self.running = self.running, ops.current(self.inst)
        for button in self.query(Button):
            button.disabled = self.running is not None
        if was and not self.running:
            self.app.notify(f"{self.inst.title}: {was.op} finished — see Operation log")
            self.refresh_state()
        if bool(was) != bool(self.running):
            self.render_info()
        if self.tail:
            path, pos = self.tail
            try:
                with open(path, "rb") as fh:
                    fh.seek(pos)
                    chunk = fh.read()
            except FileNotFoundError:
                return
            # Only whole lines: a write mid-line would otherwise split it in two.
            chunk = chunk[: chunk.rfind(b"\n") + 1]
            if chunk:
                self.tail = (path, pos + len(chunk))
                text = chunk.decode(errors="replace").rstrip("\n")
                self.query_one(".oplog", RichLog).write(Text.from_ansi(text))

    def launch(self, op: str) -> None:
        try:
            run = ops.start(self.inst, op)
        except RuntimeError as e:
            self.app.notify(str(e), severity="error")
            return
        self.running = run
        self.follow(run.log)
        self.query_one(".lower", TabbedContent).active = f"oplog-{self.inst.key}"
        self.render_info()
