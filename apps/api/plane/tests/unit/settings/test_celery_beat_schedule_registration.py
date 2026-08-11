# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import importlib

import pytest
from django.conf import settings

from plane.celery import app


def _scheduled_task_names():
    """Fully qualified names of every task celery beat is configured to dispatch."""
    return {entry["task"] for entry in app.conf.beat_schedule.values()}


@pytest.mark.unit
class TestCeleryBeatScheduleRegistration:
    """Guard the beat schedule against tasks the worker cannot run.

    Task modules live in plane/bgtasks/*.py, which is not the app-level "tasks"
    module that autodiscover_tasks() looks for. A module therefore reaches the
    worker's registry only if CELERY_IMPORTS lists it, or if some unrelated view
    or signal happens to import it. When neither holds, beat dispatches the task
    on schedule and the worker discards every message as unregistered, so the
    job silently never runs and nothing surfaces except a worker-side error.
    """

    def test_every_scheduled_task_module_is_in_celery_imports(self):
        missing = sorted(
            {name.rsplit(".", 1)[0] for name in _scheduled_task_names()} - set(settings.CELERY_IMPORTS)
        )
        assert not missing, (
            "beat_schedule references task modules absent from CELERY_IMPORTS: "
            f"{missing}. Without an explicit entry the worker only registers the "
            "module by accident, so the scheduled job may never run."
        )

    def test_every_scheduled_task_is_importable_and_registered(self):
        """Importing the declared modules must make every scheduled task resolvable."""
        for module in settings.CELERY_IMPORTS:
            importlib.import_module(module)

        unresolvable = sorted(name for name in _scheduled_task_names() if name not in app.tasks)
        assert not unresolvable, (
            f"scheduled tasks are not registered after importing CELERY_IMPORTS: {unresolvable}"
        )

    def test_scheduled_task_names_point_at_real_callables(self):
        """A typo in a beat_schedule task path fails the same silent way."""
        for name in sorted(_scheduled_task_names()):
            module_path, attribute = name.rsplit(".", 1)
            module = importlib.import_module(module_path)
            assert hasattr(module, attribute), f"{module_path} has no attribute {attribute!r}"
