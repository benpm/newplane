# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Named, shareable workspace invites.

The stock invite flow emails a link. This instance has no SMTP configured, so
those invites would be created and then silently go nowhere. These endpoints
return the link instead, for an admin to send however they like, and carry the
invitee's name so the resulting account is labelled correctly on arrival.

The link and token are exactly the ones the email flow produces, so acceptance
goes through the same code path with the same validation.
"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.instance_dashboard.base import InstanceDashboardBaseView
from plane.db.models import User, Workspace, WorkspaceMember, WorkspaceMemberInvite

# Mirrors ROLE_CHOICES on the membership models: 20 admin, 15 member, 5 guest.
VALID_ROLES = {5, 15, 20}


def invite_link(invite):
    """The URL an invitee opens, identical in shape to the emailed one."""
    base = (settings.WEB_URL or "").rstrip("/")
    return f"{base}/workspace-invitations/?invitation_id={invite.id}&slug={invite.workspace.slug}&token={invite.token}"


def _serialize(invite):
    return {
        "id": str(invite.id),
        "email": invite.email,
        "display_name": invite.display_name,
        "role": invite.role,
        "workspace_id": str(invite.workspace_id),
        "workspace_slug": invite.workspace.slug,
        "workspace_name": invite.workspace.name,
        "accepted": invite.accepted,
        "responded_at": invite.responded_at,
        "created_at": invite.created_at,
        "link": invite_link(invite),
    }


class InstanceDashboardInviteEndpoint(InstanceDashboardBaseView):
    """List outstanding invites, or create a named one."""

    def get(self, request):
        invites = (
            WorkspaceMemberInvite.objects.select_related("workspace")
            .filter(responded_at__isnull=True)
            .order_by("-created_at")
        )
        workspace_id = request.query_params.get("workspace_id")
        if workspace_id:
            invites = invites.filter(workspace_id=workspace_id)

        return Response({"results": [_serialize(invite) for invite in invites]})

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        display_name = (request.data.get("display_name") or "").strip()
        workspace_id = request.data.get("workspace_id")
        role = request.data.get("role", 15)

        if not email:
            return Response({"error": "An email address is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not workspace_id:
            return Response({"error": "A workspace is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            role = int(role)
        except (TypeError, ValueError):
            role = -1
        if role not in VALID_ROLES:
            return Response(
                {"error": f"Role must be one of {sorted(VALID_ROLES)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            workspace = Workspace.objects.get(pk=workspace_id)
        except (Workspace.DoesNotExist, ValidationError, ValueError):
            # ValidationError covers a malformed UUID reaching the lookup.
            return Response({"error": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        existing_user = User.objects.filter(email__iexact=email).first()
        if (
            existing_user
            and WorkspaceMember.objects.filter(workspace=workspace, member=existing_user, is_active=True).exists()
        ):
            return Response(
                {"error": "That person is already a member of this workspace."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reuse an outstanding invite rather than colliding with the
        # (email, workspace) uniqueness constraint. Re-inviting someone is a
        # request for their link again, possibly under a corrected name.
        invite = WorkspaceMemberInvite.objects.filter(
            email__iexact=email, workspace=workspace, responded_at__isnull=True
        ).first()

        if invite:
            invite.role = role
            invite.display_name = display_name
            invite.save(update_fields=["role", "display_name"])
            reused = True
        else:
            invite = WorkspaceMemberInvite.objects.create(
                email=email,
                workspace=workspace,
                display_name=display_name,
                role=role,
                token=uuid.uuid4().hex,
                created_by=request.user,
            )
            reused = False

        return Response(
            {**_serialize(invite), "reused": reused},
            status=status.HTTP_200_OK if reused else status.HTTP_201_CREATED,
        )


class InstanceDashboardInviteDetailEndpoint(InstanceDashboardBaseView):
    """Revoke an outstanding invite."""

    def delete(self, request, pk):
        try:
            invite = WorkspaceMemberInvite.objects.get(pk=pk)
        except WorkspaceMemberInvite.DoesNotExist:
            return Response({"error": "Invite not found."}, status=status.HTTP_404_NOT_FOUND)

        if invite.responded_at is not None:
            return Response(
                {"error": "That invite has already been responded to."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
