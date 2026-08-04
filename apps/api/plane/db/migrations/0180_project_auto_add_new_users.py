from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0179_issueworklog_workspace_logged_at_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="auto_add_new_users",
            field=models.BooleanField(default=False),
        ),
    ]
