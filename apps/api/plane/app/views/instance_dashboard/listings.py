# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Paginated instance-wide inventories of workspaces, users and projects.

The god-mode equivalents (``license/api/views/{workspace,user}.py``) cannot be
reused directly — they sit behind the admin session cookie — so the annotation
and search patterns are mirrored here against the same models.
"""

from django.db.models import Count, F, Func, OuterRef, Q

from plane.app.views.instance_dashboard.base import InstanceDashboardBaseView
from plane.db.models import Issue, Project, ProjectMember, User, Workspace, WorkspaceMember
from plane.license.models import InstanceAdmin


def _subquery_count(queryset):
    """Correlated COUNT(*) for use as an annotation."""
    return queryset.order_by().annotate(count=Func(F("id"), function="Count")).values("count")


class InstanceDashboardWorkspaceListEndpoint(InstanceDashboardBaseView):
    """Every workspace with its project, member and work-item totals."""

    def get(self, request):
        workspaces = Workspace.objects.annotate(
            total_projects=_subquery_count(Project.objects.filter(workspace_id=OuterRef("id"))),
            total_members=_subquery_count(
                WorkspaceMember.objects.filter(workspace=OuterRef("id"), member__is_bot=False, is_active=True)
            ),
            total_issues=_subquery_count(Issue.objects.filter(workspace_id=OuterRef("id"))),
        ).order_by("-created_at")

        search = request.query_params.get("search", "").strip()
        if search:
            workspaces = workspaces.filter(Q(name__icontains=search) | Q(slug__icontains=search))

        return self.paginate(
            request=request,
            queryset=workspaces,
            on_results=lambda results: [
                {
                    "id": str(workspace.id),
                    "name": workspace.name,
                    "slug": workspace.slug,
                    "owner": (workspace.owner.display_name or workspace.owner.email if workspace.owner else None),
                    "logo_url": workspace.logo_url,
                    "total_projects": workspace.total_projects or 0,
                    "total_members": workspace.total_members or 0,
                    "total_issues": workspace.total_issues or 0,
                    "created_at": workspace.created_at,
                }
                for workspace in results
            ],
            default_per_page=20,
            max_per_page=100,
        )


class InstanceDashboardUserListEndpoint(InstanceDashboardBaseView):
    """Every user account with membership counts and sign-in state."""

    def get(self, request):
        admin_ids = set(InstanceAdmin.objects.filter(user__isnull=False).values_list("user_id", flat=True))

        users = User.objects.annotate(
            workspace_count=Count("member_workspace", filter=Q(member_workspace__is_active=True), distinct=True)
        ).order_by("-date_joined")

        search = request.query_params.get("search", "").strip()
        if search:
            users = users.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(display_name__icontains=search)
            )

        is_active = request.query_params.get("is_active")
        if is_active is not None:
            users = users.filter(is_active=is_active.lower() == "true")

        return self.paginate(
            request=request,
            queryset=users,
            on_results=lambda results: [
                {
                    "id": str(user.id),
                    "email": user.email,
                    "display_name": user.display_name,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "avatar_url": user.avatar_url,
                    "is_active": user.is_active,
                    "is_bot": user.is_bot,
                    "is_instance_admin": user.id in admin_ids,
                    "workspace_count": user.workspace_count,
                    "date_joined": user.date_joined,
                    "last_login": user.last_login,
                }
                for user in results
            ],
            default_per_page=20,
            max_per_page=100,
        )


class InstanceDashboardProjectListEndpoint(InstanceDashboardBaseView):
    """Every project across every workspace."""

    def get(self, request):
        projects = (
            Project.objects.select_related("workspace", "project_lead")
            .annotate(
                member_count=_subquery_count(
                    ProjectMember.objects.filter(project_id=OuterRef("id"), is_active=True, member__is_bot=False)
                ),
                issue_count=_subquery_count(Issue.objects.filter(project_id=OuterRef("id"))),
            )
            .order_by("-created_at")
        )

        workspace_id = request.query_params.get("workspace_id")
        if workspace_id:
            projects = projects.filter(workspace_id=workspace_id)

        search = request.query_params.get("search", "").strip()
        if search:
            projects = projects.filter(Q(name__icontains=search) | Q(identifier__icontains=search))

        return self.paginate(
            request=request,
            queryset=projects,
            on_results=lambda results: [
                {
                    "id": str(project.id),
                    "name": project.name,
                    "identifier": project.identifier,
                    "workspace_id": str(project.workspace_id),
                    "workspace_slug": project.workspace.slug,
                    "workspace_name": project.workspace.name,
                    "lead": (
                        project.project_lead.display_name or project.project_lead.email
                        if project.project_lead
                        else None
                    ),
                    "network": project.network,
                    "is_global": project.is_global,
                    "is_archived": project.archived_at is not None,
                    "member_count": project.member_count or 0,
                    "issue_count": project.issue_count or 0,
                    "created_at": project.created_at,
                }
                for project in results
            ],
            default_per_page=20,
            max_per_page=100,
        )
