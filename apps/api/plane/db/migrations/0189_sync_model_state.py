# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Catch up the migration state with the models, after months of drift.

31 of these 32 operations emit no SQL at all. They record model attributes that
Postgres never sees — ``related_name``, ``verbose_name``, ``help_text``,
``choices`` labels, Meta ``ordering`` — all of which live in
``Field.non_db_attrs``, so ``_field_should_be_altered()`` returns False and the
schema editor is never entered. The seven ``AlterField`` operations on ``id``
are the only ones that reach ``_alter_field``, and every branch inside is
skipped because a primary key is already unique; they exist because eight
hand-written ``CreateModel`` migrations transcribed ``BaseModel.id`` by hand and
dropped ``db_index=True``.

The single operation that touches the database is the ``RenameIndex`` on
``issueworklog``: migration 0179 hand-picked ``issue_workl_workspa_logged_idx``,
which is not a name the autodetector would ever generate, so it has been
proposing this rename ever since. 0137 resolved exactly this situation the same
way for the two sibling indexes on the same table. ``ALTER INDEX ... RENAME`` is
a catalog-only operation.

Not included, deliberately: the autodetector also wanted to drop
``department_unique_code`` and ``department_unique_dept_code`` and make
``departments.code`` nullable. Those three came from an unrelated commit editing
the model with no migration; the database, migrations 0136/0139 and the
serializer all agreed with each other, so the model was corrected instead.

``plane/tests/unit/db/test_migrations_in_sync.py`` now fails the build if models
and migrations diverge again.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0188_github_link_unique_when_not_deleted'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='maintaskcategory',
            options={'ordering': ['sort_order', 'name'], 'verbose_name': 'Main Task Category', 'verbose_name_plural': 'Main Task Categories'},
        ),
        migrations.AlterModelOptions(
            name='projectcopyjob',
            options={'ordering': ('-created_at',), 'verbose_name': 'Project Copy Job', 'verbose_name_plural': 'Project Copy Jobs'},
        ),
        migrations.AlterModelOptions(
            name='subtaskcategory',
            options={'ordering': ['sort_order', 'name'], 'verbose_name': 'Sub Task Category', 'verbose_name_plural': 'Sub Task Categories'},
        ),
        migrations.RenameIndex(
            model_name='issueworklog',
            new_name='issue_workl_workspa_2af7b4_idx',
            old_name='issue_workl_workspa_logged_idx',
        ),
        migrations.AlterField(
            model_name='capacityexportjob',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By'),
        ),
        migrations.AlterField(
            model_name='capacityexportjob',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='capacityexportjob',
            name='updated_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By'),
        ),
        migrations.AlterField(
            model_name='dayoverride',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Deleted At'),
        ),
        migrations.AlterField(
            model_name='dayoverride',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='departmenttaskcategory',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By'),
        ),
        migrations.AlterField(
            model_name='departmenttaskcategory',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='departmenttaskcategory',
            name='updated_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By'),
        ),
        migrations.AlterField(
            model_name='hoexportjob',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By'),
        ),
        migrations.AlterField(
            model_name='hoexportjob',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='hoexportjob',
            name='updated_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By'),
        ),
        migrations.AlterField(
            model_name='holiday',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Deleted At'),
        ),
        migrations.AlterField(
            model_name='holiday',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='moduleactivity',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Created At'),
        ),
        migrations.AlterField(
            model_name='moduleactivity',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Deleted At'),
        ),
        migrations.AlterField(
            model_name='moduleactivity',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Last Modified At'),
        ),
        migrations.AlterField(
            model_name='projectcopyjob',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By'),
        ),
        migrations.AlterField(
            model_name='projectcopyjob',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='projectcopyjob',
            name='updated_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By'),
        ),
        migrations.AlterField(
            model_name='projectfieldpermission',
            name='created_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By'),
        ),
        migrations.AlterField(
            model_name='projectfieldpermission',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='projectfieldpermission',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_%(class)s', to='db.project'),
        ),
        migrations.AlterField(
            model_name='projectfieldpermission',
            name='updated_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By'),
        ),
        migrations.AlterField(
            model_name='projectfieldpermission',
            name='workspace',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workspace_%(class)s', to='db.workspace'),
        ),
        migrations.AlterField(
            model_name='state',
            name='group',
            field=models.CharField(choices=[('backlog', 'Backlog'), ('unstarted', 'Unstarted'), ('started', 'Started'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('triage', 'Triage')], default='backlog', max_length=20),
        ),
        migrations.AlterField(
            model_name='workschedule',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Deleted At'),
        ),
        migrations.AlterField(
            model_name='workschedule',
            name='id',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True),
        ),
        migrations.AlterField(
            model_name='workschedule',
            name='workspace',
            field=models.ForeignKey(blank=True, help_text='NULL = instance-level default; set to scope per workspace.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='work_schedules', to='db.workspace'),
        ),
    ]
