# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Shared base view for the instance dashboard.

The dashboard is instance-wide and admin-only, but it is served to *apps/web*,
not to god-mode. That rules out mounting it under ``/api/instances/``: the
session middleware (``plane.authentication.middleware.session``) picks the
cookie by testing whether ``"instances"`` appears anywhere in the request path,
so a web session (``session-id``) is invisible to any such route and every
request would resolve to ``AnonymousUser``.

Hence ``/api/instance-dashboard/`` under ``plane.app.urls``, guarded by the
plain ``InstanceAdminPermission``. That class checks the same thing the client
gate (``GET /api/users/me/instance-admin/``) checks, so the two agree; the
menu-RBAC variant would not, since it additionally filters on ``allowed_menus``.
"""

from plane.app.views.base import BaseAPIView
from plane.license.api.permissions import InstanceAdminPermission


class InstanceDashboardBaseView(BaseAPIView):
    """Read-only, instance-admin-only endpoint."""

    permission_classes = [InstanceAdminPermission]
