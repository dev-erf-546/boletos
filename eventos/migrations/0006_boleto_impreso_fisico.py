from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0005_boleto_reservado_por'),
    ]

    operations = [
        migrations.AddField(
            model_name='boleto',
            name='impreso_fisico',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='boleto',
            name='fecha_impresion_fisica',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
