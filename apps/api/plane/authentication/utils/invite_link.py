# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Redeem a reusable workspace invite link once its holder has authenticated.

The token rides in the session from the moment the visitor lands on the invite
page until authentication completes, which is what lets one code path serve
email/password, magic code and every OAuth provider alike -- the OAuth round
trip preserves the session exactly as it already preserves ``next_path``.

The token is never treated as proof of identity. It is read only after the user
is authenticated, and all it confers is membership of one workspace at one role.
"""

from django.db.models import F

from plane.db.models import WorkspaceInviteLink, WorkspaceMember
from plane.utils.exception_logger import log_exception

SESSION_KEY = "invite_link_token"


def get_active_invite_link(token):
    """The live link for a token, or None."""
    if not token:
        return None
    return WorkspaceInviteLink.objects.filter(token=token, is_active=True).select_related("workspace").first()


def stash_invite_link_token(request, token):
    """Park a link token on the session for the duration of the auth flow.

    Called before authentication begins so the token is already in place when
    ``redeem_invite_link`` runs, and so it survives an OAuth round trip.
    """
    if not token or request is None or not hasattr(request, "session"):
        return
    request.session[SESSION_KEY] = str(token)


def peek_invite_link(request):
    """The live link held in this session, without consuming it.

    Used by the signup gate, which has to decide whether to admit a brand-new
    user before there is a user to attach the membership to.
    """
    if request is None or not hasattr(request, "session"):
        return None
    return get_active_invite_link(request.session.get(SESSION_KEY))


def redeem_invite_link(user, request):
    """Join ``user`` to the workspace named by the session's invite link.

    A no-op when there is no token, the link has been revoked, or the user is
    already an active member. Never raises: a failure here must not cost the
    user their sign-in, since they are authenticated by this point.
    """
    if request is None or not hasattr(request, "session"):
        return None

    token = request.session.pop(SESSION_KEY, None)
    if not token:
        return None

    try:
        invite_link = get_active_invite_link(token)
        if invite_link is None:
            return None

        member, created = WorkspaceMember.objects.get_or_create(
            workspace=invite_link.workspace,
            member=user,
            defaults={"role": invite_link.role},
        )

        if not created:
            # Someone rejoining after being removed: revive the row, but leave
            # an existing member's role alone so a link cannot demote them.
            if not member.is_active:
                member.is_active = True
                member.role = invite_link.role
                member.save(update_fields=["is_active", "role"])
            else:
                return invite_link

        WorkspaceInviteLink.objects.filter(pk=invite_link.pk).update(uses=F("uses") + 1)
        return invite_link
    except Exception as e:
        log_exception(e)
        return None
