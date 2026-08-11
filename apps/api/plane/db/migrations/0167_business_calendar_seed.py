# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Data migration: seed the instance-level default WorkSchedule.

This originally seeded a "Vietnam Banking" schedule preloaded with MOLISA
public holidays and swap-day overrides, inherited from the fork this repo came
from. De-branding removed that regional data: the schedule is now created empty
and neutral, and operators add their own holidays through God Mode.

Rewriting an applied migration is safe here because Django tracks migrations by
name, not content — instances that already ran this one are reconciled by
0186_neutralise_business_calendar, which strips the seeded rows and renames the
schedule. Fresh installs land in that same end state directly.
"""

import uuid
from django.db import migrations

DEFAULT_SCHEDULE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def seed_business_calendar(apps, schema_editor):
    """Forward migration: create the default schedule (Mon–Fri, no holidays)."""
    WorkSchedule = apps.get_model("db", "WorkSchedule")

    if WorkSchedule.objects.filter(id=DEFAULT_SCHEDULE_ID).exists():
        return

    WorkSchedule.objects.create(
        id=DEFAULT_SCHEDULE_ID,
        name="Default Schedule",
        # Mon=True, Tue=True, Wed=True, Thu=True, Fri=True, Sat=False, Sun=False
        week_pattern=[True, True, True, True, True, False, False],
        timezone="UTC",
        is_default=True,
        country_code="",
        workspace=None,
    )


def reverse_seed_business_calendar(apps, schema_editor):
    """Reverse migration: remove seeded default schedule (cascades to holidays/overrides)."""
    WorkSchedule = apps.get_model("db", "WorkSchedule")
    WorkSchedule.objects.filter(id=DEFAULT_SCHEDULE_ID).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0166_business_calendar"),
    ]

    operations = [
        migrations.RunPython(
            seed_business_calendar,
            reverse_code=reverse_seed_business_calendar,
        ),
    ]
