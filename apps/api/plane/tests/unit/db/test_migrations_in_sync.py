# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Guard against models drifting away from their migrations.

Nothing else catches this. pytest.ini passes --nomigrations, so pytest-django
builds the test schema straight from the *models* — the migration files are
never executed by any test, and models and migrations can diverge arbitrarily
while the whole suite stays green. No CI job runs `makemigrations --check`
either.

The failure mode that follows is worth spelling out, because it has already
happened here: the test database ends up with a different schema from
production, so a test can pass in CI and the same code fail in production. The
`departments.code` column was NOT NULL in production and nullable in every test
database for five months, which is exactly how the bulk-import bug survived.
"""

import pytest
from django.apps import apps
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import MigrationQuestioner
from django.db.migrations.state import ProjectState
from django.test import override_settings


def _pending_operations():
    """Return [(app_label, operation)] the autodetector would write out."""
    # pytest-django implements --nomigrations by replacing MIGRATION_MODULES
    # with a sentinel whose __getitem__ returns None for every app, which makes
    # MigrationLoader treat every app as unmigrated — the autodetector would
    # then propose CreateModel for the entire project. An empty dict restores
    # normal <app>.migrations discovery ("db" in {} is False, so the loader
    # falls back to the default module path).
    #
    # Overriding rather than reading is also what keeps this test independent
    # of ordering: the sentinel is installed by the session-scoped
    # django_db_setup fixture, so whether it is in place when this test runs
    # otherwise depends on which tests ran first.
    with override_settings(MIGRATION_MODULES={}):
        # connection=None: no database access, and no consistency check against
        # django_migrations. This test needs neither.
        loader = MigrationLoader(None, ignore_no_migrations=True)
        autodetector = MigrationAutodetector(
            loader.project_state(),
            ProjectState.from_apps(apps),
            # The base questioner, not NonInteractiveMigrationQuestioner: the
            # latter calls sys.exit(3) on a question it cannot answer, which
            # would replace a readable diff with a bare exit code.
            MigrationQuestioner(specified_apps=set(), dry_run=True),
        )
        changes = autodetector.changes(graph=loader.graph, trim_to_apps=None, convert_apps=None)

        # Only apps that actually ship migrations. plane.tests is appended to
        # INSTALLED_APPS by the test settings and has no migrations package, so
        # it would otherwise read as "needs an initial migration" forever.
        return [
            (app_label, operation)
            for app_label, migrations in sorted(changes.items())
            if app_label in loader.migrated_apps
            for migration in migrations
            for operation in migration.operations
        ]


@pytest.mark.unit
def test_no_model_changes_are_missing_a_migration():
    pending = _pending_operations()
    if not pending:
        return

    listing = "\n".join(f"  {app_label}: {operation.describe()}" for app_label, operation in pending)
    pytest.fail(
        f"{len(pending)} model change(s) have no migration.\n\n"
        "Either generate one:\n"
        "    python manage.py makemigrations\n"
        "or, if the database is the authoritative side and the model was\n"
        "changed by mistake, fix the model instead.\n\n"
        f"Pending operations:\n{listing}"
    )
