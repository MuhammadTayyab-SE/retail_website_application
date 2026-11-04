from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("checkout", "0002_deliverypolicy_pickup_enabled_and_more")]

    operations = [
        migrations.AddField(
            model_name="deliverypolicy",
            name="return_address",
            field=models.TextField(blank=True, default="", max_length=1000),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
