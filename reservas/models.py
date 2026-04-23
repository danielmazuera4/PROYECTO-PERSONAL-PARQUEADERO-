from django.db import models
from django.contrib.auth.models import User

class Reserva(models.Model):
    TIPO_CHOICES = [
        ('CARRO', 'Carro'),
        ('MOTO', 'Moto'),
    ]
    MODALIDAD_CHOICES = [
        ('DIA_HORA', 'Día/Hora'),
        ('MENSUALIDAD', 'Mensualidad'),
    ]

    # --- CAMPOS DE USUARIO ---
    operario = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reservas_atendidas'
    )
    usuario_registro = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='reservas_creadas'
    )

    # --- DATOS DEL VEHÍCULO ---
    placa = models.CharField(max_length=10)
    tipo_vehiculo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='CARRO')
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES, default='DIA_HORA')
    
    # --- FECHAS Y ESTADO ---
    fecha_entrada = models.DateTimeField(null=True, blank=True)
    fecha_salida = models.DateTimeField(null=True, blank=True)
    fecha_vencimiento = models.DateTimeField(null=True, blank=True)
    
    # Campo clave para tu nueva tabla: Diferencia el recibo de pago de un simple movimiento
    es_pago_mensualidad = models.BooleanField(default=False)
    
    # Identifica si este registro es solo para guardar salida (cuando difiere el usuario que ingresó vs el que sacó)
    registra_solo_salida = models.BooleanField(default=False)
    
    activo = models.BooleanField(default=True)
    
    # Decimales en 0 para manejar pesos colombianos sin centavos
    total_pagar = models.DecimalField(max_digits=10, decimal_places=0, default=0)

    class Meta:
        ordering = ['-fecha_entrada'] # Lo más reciente arriba siempre

    def __str__(self):
        nombre_usuario = self.usuario_registro.username if self.usuario_registro else 'Sin usuario'
        return f"{self.placa} - {nombre_usuario} - {self.fecha_entrada.strftime('%Y-%m-%d %H:%M')}"

    # Método de ayuda para tu tabla de control mensual
    def obtener_estado_texto(self):
        if self.modalidad == 'MENSUALIDAD' and self.es_pago_mensualidad:
            return "PAGO DE MENSUALIDAD"
        if not self.fecha_salida:
            return "EN EL PARQUEADERO"
        return "FUERA (Pendiente por entrar)"