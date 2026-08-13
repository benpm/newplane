# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Renaming and deactivating accounts from the instance dashboard.

Deliberately no hard delete. ``User`` is not soft-deletable, and Django
cascades deletes in Python across the ~300 relations that point at it, so
removing one real account here takes its work items, pages, projects and
activity history with it. Deactivation is reversible and costs nothing.
"""

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.instance_dashboard.base import InstanceDashboardBaseView
from plane.db.models import User, WorkspaceMember
from plane.license.models import InstanceAdmin

MAX_DISPLAY_NAME_LENGTH = 255


class InstanceDashboardUserDetailEndpoint(InstanceDashboardBaseView):
    """Rename an account, or deactivate and reactivate it.

    ``username`` and ``email`` are never touched: they are the account's
    identity and its login key, and existing sessions and audit trails are
    keyed on them. Only the human-facing label changes.
    """

    def patch(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if "display_name" in request.data:
            error = self._rename(user, request.data["display_name"])
            if error:
                return error

        if "is_active" in request.data:
            error = self._set_active(request, user, bool(request.data["is_active"]))
            if error:
                return error

        return Response(
            {
                "id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "is_active": user.is_active,
            }
        )

    @staticmethod
    def _rename(user, raw_name):
        display_name = (raw_name or "").strip()
        if not display_name:
            return Response(
                {"error": "Display name cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(display_name) > MAX_DISPLAY_NAME_LENGTH:
            return Response(
                {"error": f"Display name cannot exceed {MAX_DISPLAY_NAME_LENGTH} characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.display_name = display_name
        user.save(update_fields=["display_name"])
        return None

    @staticmethod
    def _set_active(request, user, is_active):
        if not is_active:
            # Locking yourself out of the instance is never the intent, and
            # recovering from it needs shell access.
            if user.id == request.user.id:
                return Response(
                    {"error": "You cannot deactivate your own account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if _is_last_active_super_admin(user):
                return Response(
                    {"error": "This is the last active super admin — deactivating it would lock God Mode."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            user.is_active = is_active
            user.save(update_fields=["is_active"])
            # Workspace membership follows the account, so a deactivated user
            # also disappears from member lists and pickers rather than
            # lingering as an unusable option.
            #
            # Reactivation restores every membership. A member who had been
            # removed from one workspace before the account was deactivated
            # comes back to it — rare, and one click to undo, which is a better
            # trade than persisting per-membership state for this.
            WorkspaceMember.objects.filter(member=user).update(is_active=is_active)

        return None


def _is_last_active_super_admin(user):
    """True when deactivating this user would leave no super admin able to sign in."""
    if not InstanceAdmin.objects.filter(user=user, is_super_admin=True).exists():
        return False
    others = InstanceAdmin.objects.filter(is_super_admin=True, user__is_active=True).exclude(user=user)
    return not others.exists()
