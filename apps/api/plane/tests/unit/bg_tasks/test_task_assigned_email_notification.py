# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import pytest

from plane.db.models import (
    Project,
    ProjectMember,
    UserNotificationPreference,
    EmailNotificationLog,
    IssueSubscriber,
    State,
)
from plane.tests.factories import UserFactory, ProjectFactory, WorkspaceFactory, IssueFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestTaskAssignmentEmailOptions:
    def test_default_values_are_false(self):
        user = UserFactory()
        workspace = WorkspaceFactory(owner=user)
        project = ProjectFactory(workspace=workspace, project_lead=user)
        preference, _ = UserNotificationPreference.objects.get_or_create(user=user)

        assert preference.task_assigned is False
        assert project.email_on_assignment is False

    def test_email_log_not_created_when_disabled(self):
        from plane.bgtasks.notification_task import notifications

        user = UserFactory()
        actor = UserFactory()
        workspace = WorkspaceFactory(owner=user)
        project = ProjectFactory(workspace=workspace, project_lead=user)
        ProjectMember.objects.create(project=project, member=user, workspace=workspace)
        ProjectMember.objects.create(project=project, member=actor, workspace=workspace)

        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        issue = IssueFactory(project=project, workspace=workspace, state=state)
        IssueSubscriber.objects.create(issue=issue, project=project, workspace=workspace, subscriber=user)

        UserNotificationPreference.objects.filter(user=user).update(task_assigned=False, property_change=False)
        Project.objects.filter(id=project.id).update(email_on_assignment=False)

        EmailNotificationLog.objects.all().delete()

        notifications(
            type="issue.activity.created",
            issue_id=str(issue.id),
            project_id=str(project.id),
            actor_id=str(actor.id),
            subscriber=str(user.id),
            issue_activities_created=json.dumps([
                {
                    "id": "act-1",
                    "verb": "updated",
                    "field": "assignees",
                    "old_identifier": None,
                    "new_identifier": str(user.id),
                    "actor_id": str(actor.id),
                    "created_at": "2026-09-06T12:00:00Z",
                    "issue_detail": {"id": str(issue.id)},
                    "comment": "assigned issue to user",
                }
            ]),
            requested_data={},
            current_instance={},
        )

        assert EmailNotificationLog.objects.filter(receiver=user).count() == 0

    def test_email_log_created_when_user_preference_enabled(self):
        from plane.bgtasks.notification_task import notifications

        user = UserFactory()
        actor = UserFactory()
        workspace = WorkspaceFactory(owner=user)
        project = ProjectFactory(workspace=workspace, project_lead=user)
        ProjectMember.objects.create(project=project, member=user, workspace=workspace)
        ProjectMember.objects.create(project=project, member=actor, workspace=workspace)

        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        issue = IssueFactory(project=project, workspace=workspace, state=state)
        IssueSubscriber.objects.create(issue=issue, project=project, workspace=workspace, subscriber=user)

        UserNotificationPreference.objects.filter(user=user).update(task_assigned=True, property_change=False)
        Project.objects.filter(id=project.id).update(email_on_assignment=False)

        EmailNotificationLog.objects.all().delete()

        notifications(
            type="issue.activity.created",
            issue_id=str(issue.id),
            project_id=str(project.id),
            actor_id=str(actor.id),
            subscriber=str(user.id),
            issue_activities_created=json.dumps([
                {
                    "id": "act-2",
                    "verb": "updated",
                    "field": "assignees",
                    "old_identifier": None,
                    "new_identifier": str(user.id),
                    "actor_id": str(actor.id),
                    "created_at": "2026-09-06T12:00:00Z",
                    "issue_detail": {"id": str(issue.id)},
                    "comment": "assigned issue to user",
                }
            ]),
            requested_data={},
            current_instance={},
        )

        assert EmailNotificationLog.objects.filter(receiver=user).count() == 1

    def test_email_log_created_when_project_enabled(self):
        from plane.bgtasks.notification_task import notifications

        user = UserFactory()
        actor = UserFactory()
        workspace = WorkspaceFactory(owner=user)
        project = ProjectFactory(workspace=workspace, project_lead=user)
        ProjectMember.objects.create(project=project, member=user, workspace=workspace)
        ProjectMember.objects.create(project=project, member=actor, workspace=workspace)

        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        issue = IssueFactory(project=project, workspace=workspace, state=state)
        IssueSubscriber.objects.create(issue=issue, project=project, workspace=workspace, subscriber=user)

        UserNotificationPreference.objects.filter(user=user).update(task_assigned=False, property_change=False)
        Project.objects.filter(id=project.id).update(email_on_assignment=True)

        EmailNotificationLog.objects.all().delete()

        notifications(
            type="issue.activity.created",
            issue_id=str(issue.id),
            project_id=str(project.id),
            actor_id=str(actor.id),
            subscriber=str(user.id),
            issue_activities_created=json.dumps([
                {
                    "id": "act-3",
                    "verb": "updated",
                    "field": "assignees",
                    "old_identifier": None,
                    "new_identifier": str(user.id),
                    "actor_id": str(actor.id),
                    "created_at": "2026-09-06T12:00:00Z",
                    "issue_detail": {"id": str(issue.id)},
                    "comment": "assigned issue to user",
                }
            ]),
            requested_data={},
            current_instance={},
        )

        assert EmailNotificationLog.objects.filter(receiver=user).count() == 1
