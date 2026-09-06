# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models
from plane.db.models.project import ProjectBaseModel


class DiscordProjectSync(ProjectBaseModel):
    server_id = models.CharField(max_length=64)
    server_name = models.CharField(max_length=255, default="")
    channel_id = models.CharField(max_length=64, blank=True, default="")
    webhook_url = models.URLField(max_length=1000)
    bot_token = models.CharField(max_length=255, blank=True, default="")
    notify_on_create = models.BooleanField(default=True)
    notify_on_update = models.BooleanField(default=True)
    notify_on_complete = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.project.name} -> Discord Server {self.server_name} ({self.server_id})"

    class Meta:
        verbose_name = "Discord Project Sync"
        verbose_name_plural = "Discord Project Syncs"
        db_table = "discord_project_syncs"
        ordering = ("-created_at",)
