# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.db.models import WorkspaceMember, ProjectMember
from functools import wraps
from rest_framework.response import Response
from rest_framework import status

from enum import Enum


class ROLE(Enum):
    ADMIN = 20
    MEMBER = 15
    GUEST = 5


def allow_permission(allowed_roles, level="PROJECT", creator=False, model=None, assignee=False):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(instance, request, *args, **kwargs):
            # If user is anonymous, allow safe read operations on public projects
            if not request.user or request.user.is_anonymous:
                if request.method in ["GET", "HEAD", "OPTIONS"]:
                    project_id = kwargs.get("project_id")
                    if project_id:
                        from plane.db.models import Project
                        from plane.db.models.project import ProjectNetwork
                        if Project.objects.filter(
                            id=project_id,
                            network=ProjectNetwork.PUBLIC.value,
                            workspace__slug=kwargs.get("slug"),
                        ).exists():
                            return view_func(instance, request, *args, **kwargs)
                return Response(
                    {"error": "You don't have the required permissions."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Check for creator if required
            if creator and model and request.user.is_authenticated:
                obj = model.objects.filter(id=kwargs["pk"], created_by=request.user).exists()
                if obj:
                    return view_func(instance, request, *args, **kwargs)

            # Check for assignee if required
            if assignee and request.user.is_authenticated:
                from plane.db.models import IssueAssignee
                is_assignee = IssueAssignee.objects.filter(
                    issue_id=kwargs["pk"],
                    assignee=request.user,
                    deleted_at__isnull=True,
                ).exists()
                if is_assignee:
                    return view_func(instance, request, *args, **kwargs)

            # Convert allowed_roles to their values if they are enum members
            allowed_role_values = [role.value if isinstance(role, ROLE) else role for role in allowed_roles]

            # Check role permissions
            if level == "WORKSPACE":
                if WorkspaceMember.objects.filter(
                    member=request.user,
                    workspace__slug=kwargs["slug"],
                    role__in=allowed_role_values,
                    is_active=True,
                ).exists():
                    return view_func(instance, request, *args, **kwargs)
            else:
                is_user_has_allowed_role = ProjectMember.objects.filter(
                    member=request.user,
                    workspace__slug=kwargs["slug"],
                    project_id=kwargs["project_id"],
                    role__in=allowed_role_values,
                    is_active=True,
                ).exists()

                # Return if the user has the allowed role, or if they are a workspace admin (full bypass)
                if is_user_has_allowed_role:
                    return view_func(instance, request, *args, **kwargs)
                elif WorkspaceMember.objects.filter(
                    member=request.user,
                    workspace__slug=kwargs["slug"],
                    role=ROLE.ADMIN.value,
                    is_active=True,
                ).exists():
                    return view_func(instance, request, *args, **kwargs)

            # Return permission denied if no conditions are met
            return Response(
                {"error": "You don't have the required permissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return _wrapped_view

    return decorator
