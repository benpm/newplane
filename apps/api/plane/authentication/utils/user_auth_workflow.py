# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from .invite_link import redeem_invite_link
from .workspace_project_join import process_workspace_project_invitations


def post_user_auth_workflow(user, is_signup, request):
    process_workspace_project_invitations(user=user)
    # Every provider routes through here, so a link opened before signing in is
    # redeemed whether the user arrived by password, magic code or OAuth.
    redeem_invite_link(user=user, request=request)
