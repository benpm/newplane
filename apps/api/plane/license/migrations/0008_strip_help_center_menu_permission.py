# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Strip the retired "help-center" key from stored admin menu grants.

The Help Center feature is gone, so "help-center" is no longer a valid
permission key. Scoped admins whose allowed_menus still contain it would fail
_validate_menu_keys on their next PATCH (license/api/views/admin.py).
"""

from django.db import migrations

RETIRED_KEY = "help-center"


def strip_help_center(apps, schema_editor):
    InstanceAdmin = apps.get_model("license", "InstanceAdmin")
    for admin in InstanceAdmin.objects.filter(allowed_menus__contains=RETIRED_KEY).iterator():
        admin.allowed_menus = [key for key in admin.allowed_menus if key != RETIRED_KEY]
        admin.save(update_fields=["allowed_menus"])


class Migration(migrations.Migration):
    dependencies = [
        ("license", "0007_instance_admin_menu_permissions"),
    ]

    operations = [
        migrations.RunPython(strip_help_center, migrations.RunPython.noop),
    ]
