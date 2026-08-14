# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Department bulk import, around the `code` column's shape.

`departments.code` is NOT NULL, and "" is how a department says it has no code
— `department_unique_code` excludes empty strings on purpose so that any number
of code-less departments can coexist.

The importer used to normalise a missing code to None. Every such row then
violated the NOT NULL constraint, was swallowed by its own savepoint, and came
back as a "skipped" entry carrying raw Postgres error text. It went unnoticed
because the model had drifted to `null=True` and the test schema is built from
the models, so in tests the column was nullable and the constraint absent.
"""

import pytest
from django.db import IntegrityError, transaction

from plane.db.models import Department
from plane.license.api.views.department_bulk_import import _resolve_and_create


@pytest.mark.unit
@pytest.mark.django_db
class TestBulkImportCode:
    def test_a_row_without_a_code_is_created_with_an_empty_one(self):
        created, skipped = _resolve_and_create([{"name": "Facilities"}], [])

        assert skipped == []
        assert len(created) == 1
        assert created[0].code == ""
        assert Department.objects.get(name="Facilities").code == ""

    def test_many_code_less_departments_can_coexist(self):
        """The constraint's `code__gt=""` condition is what allows this."""
        created, skipped = _resolve_and_create(
            [{"name": "Facilities"}, {"name": "Catering"}, {"name": "Post Room"}], []
        )

        assert skipped == []
        assert len(created) == 3
        assert Department.objects.filter(code="").count() == 3

    def test_a_duplicate_non_empty_code_is_still_rejected(self):
        """Guards the test schema as much as the importer.

        This assertion passed vacuously for as long as the model omitted the
        constraint: --nomigrations builds the test database from the models, so
        the index the production database has been enforcing all along simply
        did not exist here.
        """
        Department.objects.create(name="Sales", code="SALES")

        with pytest.raises(IntegrityError), transaction.atomic():
            Department.objects.create(name="Sales Again", code="SALES")

    def test_a_soft_deleted_department_frees_its_code(self):
        original = Department.objects.create(name="Sales", code="SALES")
        original.delete()

        replacement = Department.objects.create(name="Sales", code="SALES")

        assert replacement.pk is not None
