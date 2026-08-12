# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Access control for the instance dashboard.

Two things are under test:

1. Only instance admins get in — anonymous and ordinary authenticated users
   are refused on every endpoint.
2. No dashboard route contains the substring ``instances``. That is not
   cosmetic: the session middleware switches cookies on it, and a route that
   matched would be unreachable for the very users this feature is for.
"""

import uuid

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from plane.app.urls.instance_dashboard import urlpatterns as dashboard_urlpatterns
from plane.db.models import User
from plane.license.models import Instance, InstanceAdmin

# Every route, as (url name, whether it accepts POST).
DASHBOARD_ROUTES = [
    ("instance-dashboard-health", False),
    ("instance-dashboard-overview", False),
    ("instance-dashboard-storage", False),
    ("instance-dashboard-bucket-scan", True),
    ("instance-dashboard-workspaces", False),
    ("instance-dashboard-users", False),
    ("instance-dashboard-projects", False),
    ("instance-dashboard-scheduled-jobs", False),
]


def _make_user(prefix: str) -> User:
    return User.objects.create(
        email=f"{prefix}-{uuid.uuid4().hex[:8]}@example.com",
        username=uuid.uuid4().hex,
        display_name=prefix,
    )


@pytest.fixture
def instance(db):
    return Instance.objects.create(
        instance_name="Test Instance",
        is_setup_done=True,
        last_checked_at=timezone.now(),
    )


@pytest.fixture
def admin_user(db, instance):
    user = _make_user("dashboard-admin")
    InstanceAdmin.objects.create(instance=instance, user=user, role=20, is_super_admin=True)
    return user


@pytest.fixture
def plain_user(db, instance):
    return _make_user("plain")


def test_dashboard_routes_never_contain_the_instances_substring():
    """The routing invariant the whole feature depends on.

    plane/authentication/middleware/session.py reads the *admin* session
    cookie ("admin-session-id") whenever "instances" appears anywhere in
    request.path, and the app cookie ("session-id") otherwise. The dashboard
    is served to apps/web, whose users hold the app cookie.

    So a path such as /api/instances-dashboard/health/ would send the
    middleware looking for a cookie the browser does not have, produce an
    empty session, resolve AnonymousUser, and return 403 to a signed-in
    instance admin — with nothing in the logs to explain why.

    If this fails, rename the route back rather than "fixing" the test.
    """
    for pattern in dashboard_urlpatterns:
        path = f"/api/{pattern.pattern}"
        assert "instances" not in path, (
            f"Route {path} contains 'instances'. The session middleware would "
            f"read the god-mode cookie for it and every web request would 403."
        )


@pytest.mark.parametrize("url_name,allows_post", DASHBOARD_ROUTES)
def test_anonymous_is_refused(db, instance, url_name, allows_post):
    client = APIClient()
    assert client.get(reverse(url_name)).status_code in (401, 403)
    if allows_post:
        assert client.post(reverse(url_name)).status_code in (401, 403)


@pytest.mark.parametrize("url_name,allows_post", DASHBOARD_ROUTES)
def test_authenticated_non_admin_is_refused(db, plain_user, url_name, allows_post):
    client = APIClient()
    client.force_authenticate(user=plain_user)
    assert client.get(reverse(url_name)).status_code == 403
    if allows_post:
        assert client.post(reverse(url_name)).status_code == 403


@pytest.mark.parametrize("url_name,_allows_post", DASHBOARD_ROUTES)
def test_instance_admin_is_allowed(db, admin_user, url_name, _allows_post):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    response = client.get(reverse(url_name))
    assert response.status_code == 200, f"{url_name} returned {response.status_code}"


def test_scoped_admin_without_menus_still_reaches_the_dashboard(db, instance):
    """A non-super admin is still an instance admin here.

    The dashboard deliberately uses InstanceAdminPermission rather than the
    menu-RBAC class: the client-side gate (GET /api/users/me/instance-admin/)
    checks only for an InstanceAdmin row, so gating the API on allowed_menus
    would show the page to someone the API then refuses.
    """
    user = _make_user("scoped-admin")
    InstanceAdmin.objects.create(instance=instance, user=user, role=20, is_super_admin=False, allowed_menus=[])

    client = APIClient()
    client.force_authenticate(user=user)
    assert client.get(reverse("instance-dashboard-overview")).status_code == 200
