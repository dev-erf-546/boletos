from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0003_boleto_vendido_por'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LoteBoletosMasivo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('total_boletos', models.PositiveIntegerField(default=0)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lotes_masivos_creados', to=settings.AUTH_USER_MODEL)),
                ('participante', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lotes_masivos', to='eventos.participante')),
                ('rifa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lotes_masivos', to='eventos.rifa')),
            ],
            options={
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.AddField(
            model_name='boleto',
            name='lote_masivo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='boletos', to='eventos.loteboletosmasivo'),
        ),
    ]
