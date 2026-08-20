"""Add ``users.discord_username``.

Members coordinate on Discord, and there was no way to find someone's handle
from inside Plane. The column holds the handle only -- Discord has no public
profile URL keyed by username (``discord.com/users/<id>`` wants the numeric
snowflake), so the UI copies the handle to the clipboard rather than pretending
to link to a profile. 32 characters is Discord's own limit.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0190_remove_workspace_is_board_of_director_workspace'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='discord_username',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
    ]
