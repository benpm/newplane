# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models

# Module imports
from plane.db.models.project import ProjectBaseModel

GITHUB_ISSUE_STATE_CHOICES = (("open", "Open"), ("closed", "Closed"))


class ProjectGithubSync(ProjectBaseModel):
    """Associates a project with a single GitHub repository for issue and wiki sync.

    Distinct from the legacy GithubRepository/GithubRepositorySync models, which are
    welded to the removed WorkspaceIntegration framework. Authentication is instance-wide
    via the GITHUB_PERSONAL_ACCESS_TOKEN environment variable, so no credentials live here.
    """

    repository_owner = models.CharField(max_length=255)
    repository_name = models.CharField(max_length=255)
    is_issue_sync_enabled = models.BooleanField(default=True)
    is_wiki_sync_enabled = models.BooleanField(default=False)
    # poll cursor: passed as `since` to the GitHub issues API
    issues_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=255, null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Project GitHub Sync"
        verbose_name_plural = "Project GitHub Syncs"
        db_table = "project_github_syncs"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["project"],
                condition=models.Q(deleted_at__isnull=True),
                name="project_github_sync_unique_project_when_deleted_at_null",
            )
        ]

    @property
    def repository_full_name(self):
        return f"{self.repository_owner}/{self.repository_name}"

    def __str__(self):
        return f"{self.project.name} <-> {self.repository_full_name}"


class GithubIssueLink(ProjectBaseModel):
    """Maps one Plane issue to one GitHub issue.

    `github_state` records the GitHub-side state as last observed or pushed. It is the
    loop suppressor for bidirectional close/reopen: a push only fires when Plane's
    done-ness disagrees with it, and applying a GitHub-originated change updates it
    before touching the Plane issue — so echo updates converge instead of ping-ponging.
    """

    github_sync = models.ForeignKey("db.ProjectGithubSync", on_delete=models.CASCADE, related_name="issue_links")
    issue = models.OneToOneField("db.Issue", on_delete=models.CASCADE, related_name="github_link")
    github_issue_number = models.IntegerField()
    github_state = models.CharField(max_length=30, choices=GITHUB_ISSUE_STATE_CHOICES, default="open")
    github_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "GitHub Issue Link"
        verbose_name_plural = "GitHub Issue Links"
        db_table = "github_issue_links"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["github_sync", "github_issue_number"],
                condition=models.Q(deleted_at__isnull=True),
                name="github_issue_link_unique_sync_number_when_deleted_at_null",
            )
        ]

    def __str__(self):
        return f"{self.github_sync.repository_full_name}#{self.github_issue_number}"
