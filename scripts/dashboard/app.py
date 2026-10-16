"""Plane instance dashboard — the Textual app shell."""

from __future__ import annotations

from typing import ClassVar

import ops
from changes_view import ChangeLog
from docker_state import git_summary
from instances import INSTANCES
from pane import InstancePane
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Static, TabbedContent, TabPane


class Confirm(ModalScreen[bool]):
    BINDINGS: ClassVar = [Binding("escape", "dismiss(False)", "cancel")]

    def __init__(self, title: str, body: str, label: str, variant: str):
        super().__init__()
        self.title_text, self.body, self.label, self.variant = (
            title,
            body,
            label,
            variant,
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(self.title_text, id="dialog-title")
            yield Static(self.body)
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", id="no")
                yield Button(self.label, id="yes", variant=self.variant)

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class PlaneDash(App):
    TITLE = "Plane instances"
    CSS_PATH = "dash.tcss"
    BINDINGS: ClassVar = [
        Binding("q", "quit", "quit"),
        Binding("r", "refresh", "refresh"),
        Binding("n", "toggle_noise", "noisy tables"),
        *(
            Binding(str(n), f"show('{i.key}')", i.title)
            for n, i in enumerate(INSTANCES, 1)
        ),
    ]

    git = "…"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(id="instances"):
            for inst in INSTANCES:
                with TabPane(f"{inst.title} · {inst.project}", id=inst.key):
                    yield InstancePane(inst)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_git()
        self.set_interval(30, self.refresh_git)

    @work(thread=True, exclusive=True, group="git")
    def refresh_git(self) -> None:
        self.git = git_summary()

    def current_pane(self) -> InstancePane:
        active = self.query_one("#instances", TabbedContent).active
        return self.query_one(f"#{active} InstancePane", InstancePane)

    def action_show(self, key: str) -> None:
        self.query_one("#instances", TabbedContent).active = key

    def action_refresh(self) -> None:
        self.current_pane().refresh_state()

    def action_toggle_noise(self) -> None:
        for log in self.query(ChangeLog):
            log.show_noise = not log.show_noise
            log.rerender()
        state = "shown" if log.show_noise else "hidden"
        self.notify(
            f"noisy tables (celery beat, sessions, recent visits, github sync) {state}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not (event.button.id or "").startswith("op-"):
            return
        pane = event.button.query_ancestor(InstancePane)
        op = ops.OPS_BY_KEY[event.button.id.removeprefix("op-")]
        inst = pane.inst
        warn = "\n\n[b red]This is PRODUCTION.[/]" if inst.key == "prod" else ""
        body = f"{op.summary}\n\nInstance: [b]{inst.title}[/] ({inst.project}, {inst.url}){warn}"
        self.push_screen(
            Confirm(f"{op.label} {inst.title}?", body, op.label, op.variant),
            lambda ok: ok and pane.launch(op.key),
        )


def main() -> None:
    PlaneDash().run()
