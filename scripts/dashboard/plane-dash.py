#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["textual>=6,<9"]
# ///
"""Live TUI dashboard for the Plane instances on this host.

    scripts/dashboard/plane-dash.py                 run in the current terminal
    zellij --layout scripts/dashboard/plane-dash.kdl   open in a zellij session

PLANE_ROOT overrides the checkout operations build from (default /home/beb/live/plane).
"""

from app import main

if __name__ == "__main__":
    main()
