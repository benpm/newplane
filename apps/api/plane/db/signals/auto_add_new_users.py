"""
Auto-enrolment signals for projects flagged with `auto_add_new_users`.

Two entry points cover the two ways a user can become new to a project:

1. A brand-new instance user  -> joined to every workspace owning a flagged project.
2. A brand-new workspace member -> joined to that workspace's flagged projects.

(1) deliberately does not touch ProjectMember itself. It only creates the
WorkspaceMember row, which re-triggers (2) — a project membership is invisible
without workspace membership (project permission checks and the project list
queryset both gate on WorkspaceMember), so the two always travel together.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

# Auto-enrolled users always land as project Member regardless of workspace role.
PROJECT_MEMBER_ROLE = 15
WORKSPACE_MEMBER_ROLE = 15


@receiver(post_save, sender="db.WorkspaceMember")
def auto_add_member_to_flagged_projects(sender, instance, created, **kwargs):
    """Join a new workspace member to every project in that workspace flagged for auto-add."""
    if not created or not instance.is_active:
        return

    from plane.db.models import Project, ProjectMember, ProjectUserProperty  # avoid circular imports

    projects = list(Project.objects.filter(workspace_id=instance.workspace_id, auto_add_new_users=True))
    if not projects:
        return

    existing_project_ids = set(
        ProjectMember.objects.filter(
            project__workspace_id=instance.workspace_id, member_id=instance.member_id
        ).values_list("project_id", flat=True)
    )

    new_members = [
        ProjectMember(
            project=project,
            workspace_id=instance.workspace_id,  # required: bulk_create bypasses ProjectBaseModel.save()
            member_id=instance.member_id,
            role=PROJECT_MEMBER_ROLE,
            created_by=instance.created_by,
        )
        for project in projects
        if project.id not in existing_project_ids
    ]

    if not new_members:
        return

    ProjectMember.objects.bulk_create(new_members, ignore_conflicts=True)

    # bulk_create bypasses ProjectMember.save() which normally creates ProjectUserProperty;
    # create it explicitly so the member's per-project issue display preferences exist.
    ProjectUserProperty.objects.bulk_create(
        [
            ProjectUserProperty(
                project=member.project,
                workspace_id=instance.workspace_id,
                user_id=instance.member_id,
                created_by=instance.created_by,
            )
            for member in new_members
        ],
        ignore_conflicts=True,
    )


@receiver(post_save, sender="db.User")
def auto_join_workspaces_for_new_user(sender, instance, created, **kwargs):
    """Join a brand-new instance user to every workspace that owns a flagged project."""
    if not created or instance.is_bot:
        return

    from plane.db.models import Project, WorkspaceMember  # avoid circular imports

    workspace_ids = set(Project.objects.filter(auto_add_new_users=True).values_list("workspace_id", flat=True))
    if not workspace_ids:
        return

    workspace_ids -= set(
        WorkspaceMember.objects.filter(workspace_id__in=workspace_ids, member_id=instance.id).values_list(
            "workspace_id", flat=True
        )
    )

    # Deliberately one create() per workspace rather than bulk_create: bulk_create skips
    # post_save, and auto_add_member_to_flagged_projects above is what enrols the projects.
    for workspace_id in workspace_ids:
        WorkspaceMember.objects.create(workspace_id=workspace_id, member_id=instance.id, role=WORKSPACE_MEMBER_ROLE)
