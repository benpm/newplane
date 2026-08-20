# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Add ``workspace_invite_links``.

Every invite up to now has been a ``WorkspaceMemberInvite``: keyed to one email
address, unique per workspace, and deleted the moment it is accepted. That
shape cannot back a single link handed to several people, which is what
onboarding a group actually needs.

This table is that link -- one token, any number of redemptions, valid until an
admin revokes it. ``uses`` is recorded for display only; there is deliberately
no cap and no expiry.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0191_user_discord_username'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkspaceInviteLink',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('token', models.CharField(db_index=True, max_length=64, unique=True)),
                ('role', models.PositiveSmallIntegerField(choices=[(20, 'Admin'), (15, 'Member'), (5, 'Guest')], default=15)),
                ('is_active', models.BooleanField(default=True)),
                ('uses', models.PositiveIntegerField(default=0)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invite_links', to='db.workspace')),
            ],
            options={
                'verbose_name': 'Workspace Invite Link',
                'verbose_name_plural': 'Workspace Invite Links',
                'db_table': 'workspace_invite_links',
                'ordering': ('-created_at',),
            },
        ),
    ]
