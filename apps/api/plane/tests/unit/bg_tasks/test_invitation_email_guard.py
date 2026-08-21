# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit tests for the unconfigured-SMTP guard on the invitation tasks.

This instance runs without SMTP, so every invitation email used to end in a bare
ConnectionRefusedError logged as an exception -- an outage-shaped traceback for
what is really a missing setting. The tasks now check is_email_configured() and
return with an explanatory warning instead.

The guard sits *after* the rendered body is written to the invite row, because
that saved text is how an admin passes an invitation on by hand when there is no
mail server. A guard placed any earlier would take that away.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from plane.license.utils.instance_value import is_email_configured


@pytest.mark.unit
class TestIsEmailConfigured:
    """EMAIL_HOST is the single value that decides whether sending can work."""

    @pytest.mark.parametrize("host", ["", "   ", None])
    def test_absent_host_reads_as_unconfigured(self, host):
        with patch(
            "plane.license.utils.instance_value.get_email_configuration",
            return_value=(host, "user", "pass", "587", "1", "0", "from@example.com"),
        ):
            assert is_email_configured() is False

    def test_present_host_reads_as_configured(self):
        with patch(
            "plane.license.utils.instance_value.get_email_configuration",
            return_value=("smtp.example.com", "user", "pass", "587", "1", "0", "from@example.com"),
        ):
            assert is_email_configured() is True


@pytest.mark.unit
@pytest.mark.django_db
class TestWorkspaceInvitationGuard:
    """The task must not dial SMTP when there is nothing to dial."""

    def _invite(self):
        from plane.db.models import WorkspaceMemberInvite
        from plane.tests.factories import UserFactory, WorkspaceFactory

        inviter = UserFactory()
        workspace = WorkspaceFactory(owner=inviter)
        return inviter, WorkspaceMemberInvite.objects.create(
            email="invitee@example.com",
            workspace=workspace,
            token="tok-guard-test",
            role=15,
            created_by=inviter,
        )

    def test_no_connection_is_opened_when_smtp_is_unset(self):
        from plane.bgtasks.workspace_invitation_task import workspace_invitation

        inviter, invite = self._invite()

        with (
            patch("plane.bgtasks.workspace_invitation_task.is_email_configured", return_value=False),
            patch("plane.bgtasks.workspace_invitation_task.get_connection") as mock_conn,
        ):
            workspace_invitation(
                invite.email,
                str(invite.workspace_id),
                invite.token,
                "https://example.com",
                inviter.email,
            )

        mock_conn.assert_not_called()

    def test_the_invitation_body_is_still_saved_for_manual_delivery(self):
        from plane.bgtasks.workspace_invitation_task import workspace_invitation

        inviter, invite = self._invite()

        with (
            patch("plane.bgtasks.workspace_invitation_task.is_email_configured", return_value=False),
            patch("plane.bgtasks.workspace_invitation_task.get_connection"),
        ):
            workspace_invitation(
                invite.email,
                str(invite.workspace_id),
                invite.token,
                "https://example.com",
                inviter.email,
            )

        invite.refresh_from_db()
        assert invite.message, "the rendered invitation text must survive the guard"

    def test_connection_is_opened_when_smtp_is_set(self):
        """Negative control: the guard must not swallow a working configuration."""
        from plane.bgtasks.workspace_invitation_task import workspace_invitation

        inviter, invite = self._invite()

        with (
            patch("plane.bgtasks.workspace_invitation_task.is_email_configured", return_value=True),
            patch("plane.bgtasks.workspace_invitation_task.get_connection") as mock_conn,
            patch("plane.bgtasks.workspace_invitation_task.EmailMultiAlternatives"),
        ):
            workspace_invitation(
                invite.email,
                str(invite.workspace_id),
                invite.token,
                "https://example.com",
                inviter.email,
            )

        mock_conn.assert_called_once()
