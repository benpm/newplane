# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Instance-wide entity counts.

These counts already existed, buried inside ``license/bgtasks/tracer.py``
where they were emitted as OpenTelemetry span attributes and thrown away.
Extracted here so both telemetry and the instance dashboard read the same
numbers from one place.

Every count is a plain ``COUNT(*)`` over an indexed table, cheap enough for a
60-second cache. Soft-deleted rows are excluded by Plane's default managers.
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from plane.db.models import (
    Cycle,
    CycleIssue,
    Department,
    Issue,
    IssueComment,
    IssueView,
    Label,
    Module,
    ModuleIssue,
    Page,
    Project,
    StaffProfile,
    User,
    Workspace,
)


def telemetry_counts():
    """The nine counts the telemetry tracer reports."""
    return {
        "workspace_count": Workspace.objects.count(),
        "user_count": User.objects.count(),
        "project_count": Project.objects.count(),
        "issue_count": Issue.objects.count(),
        "module_count": Module.objects.count(),
        "cycle_count": Cycle.objects.count(),
        "cycle_issue_count": CycleIssue.objects.count(),
        "module_issue_count": ModuleIssue.objects.count(),
        "page_count": Page.objects.count(),
    }


def _work_items_by_state_group():
    """Work-item totals bucketed by state group (backlog, started, ...)."""
    rows = Issue.objects.values("state__group").annotate(total=Count("id"))
    return {(row["state__group"] or "none"): row["total"] for row in rows}


def instance_counts():
    """Everything the dashboard overview panel shows."""
    from plane.db.models import FileAsset
    from plane.license.models import InstanceAdmin

    now = timezone.now()
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    base = telemetry_counts()

    return {
        "workspaces": base["workspace_count"],
        "users": {
            "total": base["user_count"],
            "active": User.objects.filter(is_active=True).count(),
            "bots": User.objects.filter(is_bot=True).count(),
            "instance_admins": InstanceAdmin.objects.filter(user__isnull=False).count(),
            "joined_last_30d": User.objects.filter(date_joined__gte=last_30d).count(),
            "active_last_7d": User.objects.filter(last_login__gte=last_7d).count(),
        },
        "projects": {
            "total": base["project_count"],
            "archived": Project.objects.filter(archived_at__isnull=False).count(),
            "global": Project.objects.filter(is_global=True).count(),
        },
        "work_items": {
            "total": base["issue_count"],
            "by_state_group": _work_items_by_state_group(),
            "created_last_7d": Issue.objects.filter(created_at__gte=last_7d).count(),
            "created_last_30d": Issue.objects.filter(created_at__gte=last_30d).count(),
        },
        "cycles": base["cycle_count"],
        "modules": base["module_count"],
        "pages": base["page_count"],
        "comments": IssueComment.objects.count(),
        "views": IssueView.objects.count(),
        "labels": Label.objects.count(),
        "attachments": FileAsset.objects.filter(is_uploaded=True, is_deleted=False).count(),
        "departments": Department.objects.count(),
        "staff": StaffProfile.objects.count(),
    }
