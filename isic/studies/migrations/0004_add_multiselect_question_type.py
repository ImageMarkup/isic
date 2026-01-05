from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0003_alter_questionchoice_text"),
    ]

    operations = [
        migrations.AlterField(
            model_name="question",
            name="type",
            field=models.CharField(
                choices=[
                    ("select", "Select"),
                    ("multiselect", "Multiselect"),
                    ("number", "Number"),
                    ("diagnosis", "Diagnosis"),
                ],
                default="select",
                max_length=11,
            ),
        ),
    ]
