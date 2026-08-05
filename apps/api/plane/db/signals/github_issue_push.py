"""
Push trigger for GitHub issue sync: when a linked work item is saved, enqueue a task
that closes/reopens the GitHub issue if Plane's done-ness moved. The task no-ops when
states already agree, so saves originating from the pull sync don't echo back.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="db.Issue")
def push_linked_issue_state_to_github(sender, instance, created, **kwargs):
    if created:
        return  # a link can't exist yet for a brand-new issue

    from plane.db.models import GithubIssueLink  # avoid circular imports

    if not GithubIssueLink.objects.filter(issue_id=instance.id).exists():
        return

    from plane.bgtasks.github_issue_sync_task import push_issue_state_to_github

    issue_id = str(instance.id)
    transaction.on_commit(lambda: push_issue_state_to_github.delay(issue_id))
