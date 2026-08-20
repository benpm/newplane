# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Reusable workspace invite links.

The stock invite is per-email and single-use. These endpoints manage a link
that any number of people can open: admins mint one, share it, and revoke it
when they are done. Redemption itself happens after authentication, in
``plane.authentication.utils.invite_link``.
"""

import uuid

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import (
    WorkspaceInviteLinkPublicSerializer,
    WorkspaceInviteLinkSerializer,
)
from plane.app.views.base import BaseAPIView
from plane.authentication.rate_limit import AuthenticationThrottle
from plane.authentication.utils.invite_link import stash_invite_link_token
from plane.db.models import Workspace, WorkspaceInviteLink, WorkspaceMember

# Mirrors ROLE_CHOICES on the membership models: 20 admin, 15 member, 5 guest.
VALID_ROLES = {5, 15, 20}


class WorkspaceInviteLinkEndpoint(BaseAPIView):
    """Read, mint, or revoke the workspace's reusable invite link."""

    def _current(self, slug):
        return WorkspaceInviteLink.objects.filter(workspace__slug=slug, is_active=True).first()

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        invite_link = self._current(slug)
        if invite_link is None:
            return Response({"invite_link": None}, status=status.HTTP_200_OK)
        return Response(WorkspaceInviteLinkSerializer(invite_link).data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        role = request.data.get("role", 15)
        try:
            role = int(role)
        except (TypeError, ValueError):
            role = -1
        if role not in VALID_ROLES:
            return Response(
                {"error": f"Role must be one of {sorted(VALID_ROLES)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # An admin may not mint a link that outranks them.
        requesting_user = WorkspaceMember.objects.get(workspace__slug=slug, member=request.user, is_active=True)
        if role > requesting_user.role:
            return Response(
                {"error": "You cannot create an invite link with a role higher than your own."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        workspace = Workspace.objects.get(slug=slug)

        # One live link per workspace: minting a new one retires the old token
        # so a previously shared link stops working.
        WorkspaceInviteLink.objects.filter(workspace=workspace, is_active=True).update(is_active=False)

        invite_link = WorkspaceInviteLink.objects.create(
            workspace=workspace,
            token=uuid.uuid4().hex,
            role=role,
            created_by=request.user,
        )
        return Response(WorkspaceInviteLinkSerializer(invite_link).data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug):
        invite_link = self._current(slug)
        if invite_link is None:
            return Response({"error": "No active invite link."}, status=status.HTTP_404_NOT_FOUND)
        invite_link.is_active = False
        invite_link.save(update_fields=["is_active"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceInviteLinkPublicEndpoint(BaseAPIView):
    """Name the workspace behind a link, for a visitor with no account yet.

    Open by necessity -- the landing page renders before anyone has signed in.
    The response is deliberately thin and never contains the token.

    Opening a valid link also parks its token on the session. That is what lets
    every sign-up route -- email/password, magic code, and each OAuth provider
    -- redeem it without carrying the token through their own forms, and it
    survives the OAuth round trip for free. A GET with this much side effect is
    unusual, but it mirrors ``GoogleOauthInitiateEndpoint``, which likewise
    writes ``host``, ``next_path`` and ``state`` to the session on GET.
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthenticationThrottle]

    def get(self, request, token):
        invite_link = (
            WorkspaceInviteLink.objects.select_related("workspace").filter(token=token, is_active=True).first()
        )
        if invite_link is None:
            return Response(
                {"error": "This invite link is no longer valid."},
                status=status.HTTP_404_NOT_FOUND,
            )
        stash_invite_link_token(request, token)
        return Response(WorkspaceInviteLinkPublicSerializer(invite_link).data, status=status.HTTP_200_OK)
