from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservas', '0003_reserva_total_pagar'),
    ]

    operations = [
        migrations.AddField(
            model_name='reserva',
            name='modalidad',
            field=models.CharField(
                choices=[('DIA_HORA', 'Dia/Hora'), ('MENSUALIDAD', 'Mensualidad')],
                default='DIA_HORA',
                max_length=20,
            ),
        ),
    ]
