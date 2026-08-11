# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Drop the Help Center feature.

The feature shipped a Vietnamese-only article corpus inherited from the
upstream fork and has been removed wholesale. This drops the four tables and
the orphaned inline-image assets that pointed at them.

Irreversible: the article content lived in these tables and in the fixtures
tree, both of which are gone. Re-adding the feature would mean re-creating the
schema from scratch, so no backwards path is offered.
"""

from django.db import migrations


def delete_help_article_assets(apps, schema_editor):
    """Remove FileAsset rows for help-article inline images.

    These rows carry entity_type=HELP_ARTICLE_CONTENT and a NULL workspace.
    Left behind, FileAsset.asset_url would fall through to the workspace-scoped
    branch and raise AttributeError on the NULL workspace.

    The underlying S3/MinIO objects are not touched here — storage cleanup is an
    operator task (see the de-branding notes in CHANGELOG.md).
    """
    FileAsset = apps.get_model("db", "FileAsset")
    FileAsset.objects.filter(entity_type="HELP_ARTICLE_CONTENT").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0182_github_wiki_page_link"),
    ]

    operations = [
        migrations.RunPython(delete_help_article_assets, migrations.RunPython.noop),
        # Translations first — they FK onto the parent rows.
        migrations.DeleteModel(name="HelpArticleTranslation"),
        migrations.DeleteModel(name="HelpCategoryTranslation"),
        migrations.DeleteModel(name="HelpArticle"),
        migrations.DeleteModel(name="HelpCategory"),
    ]
