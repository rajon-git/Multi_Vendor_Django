# Generated by Django 5.1.4 on 2025-02-17 16:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0014_cartorderitem_coupon'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartorder',
            name='stripe_Session_id',
            field=models.CharField(blank=True, max_length=1000, null=True),
        ),
    ]
