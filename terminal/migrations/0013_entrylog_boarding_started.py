from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('terminal', '0012_entrylog_wallet_balance_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='entrylog',
            name='boarding_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
