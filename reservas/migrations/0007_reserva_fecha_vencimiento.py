from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservas', '0006_reserva_operario_alter_reserva_modalidad_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='fecha_vencimiento',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
