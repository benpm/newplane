# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.db.signals.auto_add_new_users import (
    auto_add_member_to_flagged_projects,
    auto_join_workspaces_for_new_user,
)
from plane.db.signals.github_issue_push import push_linked_issue_state_to_github
from plane.db.signals.project import create_default_view_on_project_creation
from plane.db.signals.workspace import auto_add_admin_to_all_projects

__all__ = [
    "auto_add_member_to_flagged_projects",
    "auto_join_workspaces_for_new_user",
    "create_default_view_on_project_creation",
    "auto_add_admin_to_all_projects",
    "push_linked_issue_state_to_github",
]
