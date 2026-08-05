# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import serializers

# Module imports
from plane.db.models import ProjectGithubSync

from .base import BaseSerializer


class ProjectGithubSyncSerializer(BaseSerializer):
    repository = serializers.CharField(source="repository_full_name", read_only=True)

    class Meta:
        model = ProjectGithubSync
        fields = [
            "id",
            "project",
            "workspace",
            "repository",
            "repository_owner",
            "repository_name",
            "is_issue_sync_enabled",
            "is_wiki_sync_enabled",
            "last_sync_status",
            "last_synced_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
