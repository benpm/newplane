# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Closed signup still admits the holder of a reusable invite link.

``Adapter.__check_signup`` turns away new accounts when ``ENABLE_SIGNUP`` is
"0", with one exception: someone already invited. That exception matches a
``WorkspaceMemberInvite`` row on the email address, which a link-based invite
does not have -- the token in the session *is* the invitation. Without the
carve-out an instance with signup closed would hand out invite links that
cannot be used, and the failure would surface only as a generic
SIGNUP_DISABLED at the far end of the flow.
"""

import uuid
from unittest.mock import patch

import pytest

from plane.app.permissions import ROLE
from plane.authentication.adapter.base import Adapter
from plane.authentication.adapter.error import AuthenticationException
from plane.db.models import WorkspaceInviteLink
from plane.tests.factories import UserFactory, WorkspaceFactory


class _FakeRequest:
    def __init__(self, session=None):
        self.session = session if session is not None else {}


@pytest.fixture
def invite_link(db):
    workspace = WorkspaceFactory(owner=UserFactory())
    return WorkspaceInviteLink.objects.create(
        workspace=workspace, token=uuid.uuid4().hex, role=ROLE.MEMBER.value
    )


def _check_signup(request, email="newcomer@plane.so"):
    """Drive the name-mangled private gate on a bare adapter."""
    adapter = Adapter(request=request, provider="email")
    return adapter._Adapter__check_signup(email)


@pytest.mark.unit
@pytest.mark.django_db
class TestSignupGateWithInviteLink:
    def test_closed_signup_turns_away_a_stranger(self):
        with patch(
            "plane.authentication.adapter.base.get_configuration_value",
            return_value=("0",),
        ):
            with pytest.raises(AuthenticationException) as exc:
                _check_signup(_FakeRequest())
        assert exc.value.error_message == "SIGNUP_DISABLED"

    def test_closed_signup_admits_an_invite_link_holder(self, invite_link):
        with patch(
            "plane.authentication.adapter.base.get_configuration_value",
            return_value=("0",),
        ):
            assert _check_signup(_FakeRequest({"invite_link_token": invite_link.token})) is True

    def test_a_revoked_link_does_not_open_the_gate(self, invite_link):
        invite_link.is_active = False
        invite_link.save(update_fields=["is_active"])

        with patch(
            "plane.authentication.adapter.base.get_configuration_value",
            return_value=("0",),
        ):
            with pytest.raises(AuthenticationException):
                _check_signup(_FakeRequest({"invite_link_token": invite_link.token}))

    def test_open_signup_is_unaffected(self):
        with patch(
            "plane.authentication.adapter.base.get_configuration_value",
            return_value=("1",),
        ):
            assert _check_signup(_FakeRequest()) is True
