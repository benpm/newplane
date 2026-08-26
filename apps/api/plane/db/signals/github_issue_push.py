"""Immediate GitHub pushes triggered by saving a work item.

Two jobs, both deliberately narrow:

*State* — when a linked work item is saved, enqueue a task that closes/reopens the
GitHub issue if Plane's done-ness moved. The task no-ops when states already agree,
so saves originating from the pull sync don't echo back.

*Creation* — when a work item is created in a project with issue sync enabled,
enqueue its GitHub issue after a short delay. The delay is load-bearing: at
post_save the work item is half-built, since assignees, labels,
description_binary/description_json are written by later statements in the same
view and copy_s3_objects_of_description_and_assets rewrites description_html
asynchronously afterwards. Firing immediately would push a body that is about to
change. This is only a fast path -- the five-minute reconcile in
github_issue_sync_task is what actually guarantees creation, because bulk_create
never fires post_save at all.

*Content is deliberately absent.* Title and description reconcile only in the sweep.
Pushing them from here would fire on the pull path's own issue.save(), which is
exactly the echo the content hash exists to suppress.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

# Long enough for the creating request to finish writing the rest of the work item.
CREATE_PUSH_DELAY_SECONDS = 30


@receiver(post_save, sender="db.Issue")
def push_linked_issue_state_to_github(sender, instance, created, **kwargs):
    from plane.db.models import GithubIssueLink  # avoid circular imports

    if created:
        _enqueue_create(instance)
        return  # a link can't exist yet for a brand-new issue

    if not GithubIssueLink.objects.filter(issue_id=instance.id).exists():
        return

    from plane.bgtasks.github_issue_sync_task import push_issue_state_to_github

    issue_id = str(instance.id)
    transaction.on_commit(lambda: push_issue_state_to_github.delay(issue_id))


def _enqueue_create(instance):
    """Fast-path a new work item onto GitHub, if its project is connected."""
    from plane.db.models import ProjectGithubSync

    if getattr(instance, "is_draft", False) or getattr(instance, "archived_at", None):
        return
    if not ProjectGithubSync.objects.filter(
        project_id=instance.project_id, is_issue_sync_enabled=True
    ).exists():
        return

    from plane.bgtasks.github_issue_sync_task import create_github_issue_for_work_item

    issue_id = str(instance.id)
    transaction.on_commit(
        lambda: create_github_issue_for_work_item.apply_async(
            (issue_id,), countdown=CREATE_PUSH_DELAY_SECONDS
        )
    )
