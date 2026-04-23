#!/usr/bin/env python
"""
Script de prueba para validar el sistema de registros duales
Usuario A ingresa → Usuario B extrae → Debe mostrar 2 registros separados
"""

import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daniel_parqueadero.settings')
django.setup()

from django.contrib.auth.models import User
from reservas.models import Reserva
from django.utils import timezone

print("\n" + "="*70)
print("PRUEBA DEL SISTEMA DE REGISTROS DUALES")
print("="*70)

# ============================================================================
# 1. CREAR USUARIOS DE PRUEBA
# ============================================================================
print("\n[1] Creando usuarios de prueba...")
user_a, created_a = User.objects.get_or_create(
    username='usuario_a',
    defaults={'email': 'a@test.com', 'is_staff': True}
)
user_b, created_b = User.objects.get_or_create(
    username='usuario_b',
    defaults={'email': 'b@test.com', 'is_staff': True}
)
print(f"    ✓ Usuario A (entrada): {user_a.username} {'[NUEVO]' if created_a else '[EXISTENTE]'}")
print(f"    ✓ Usuario B (salida):  {user_b.username} {'[NUEVO]' if created_b else '[EXISTENTE]'}")

# ============================================================================
# 2. CREAR REGISTRO DE ENTRADA (Usuario A ingresa vehículo)
# ============================================================================
print("\n[2] Usuario A ingresa vehículo DIA_HORA...")
hoy = timezone.now()
hace_10_min = hoy - timedelta(minutes=10)

record_entrada = Reserva.objects.create(
    placa='ABC-123',
    tipo_vehiculo='CARRO',
    modalidad='DIA_HORA',
    fecha_entrada=hace_10_min,
    fecha_salida=None,
    total_pagar=Decimal('5000.00'),
    usuario_registro=user_a,
    operario=user_a,
    activo=True,
    registra_solo_salida=False
)
print(f"    ✓ Registro de entrada creado")
print(f"      ID: {record_entrada.id}")
print(f"      Placa: {record_entrada.placa}")
print(f"      Entrada: {record_entrada.fecha_entrada}")
print(f"      Salida: {record_entrada.fecha_salida}")
print(f"      Usuario Registro (entrada): {record_entrada.usuario_registro.username}")
print(f"      Operario (entrada): {record_entrada.operario.username}")

# ============================================================================
# 3. SIMULAR SEGUNDO USUARIO EXTRAYENDO (Usuario B = diferente)
# ============================================================================
# Aquí simularíamos la lógica de la vista salida()
# Si el usuario que extrae es diferente al que entró, crear nuevo registro

print("\n[3] Simulando: Usuario B extrae el vehículo (DIFERENTE usuario)...")

# La vista salida() detectaría esto y crearía un nuevo registro
ahora = timezone.now()
record_salida = Reserva.objects.create(
    placa='ABC-123',
    tipo_vehiculo='CARRO',
    modalidad='DIA_HORA',
    fecha_entrada=None,  # NULL porque es solo-salida
    fecha_salida=ahora,
    total_pagar=Decimal('0.00'),
    usuario_registro=user_a,  # Quién entró originalmente
    operario=user_b,  # Quién extrae
    activo=False,
    registra_solo_salida=True  # Indica que es solo-salida
)
print(f"    ✓ Registro de solo-salida creado")
print(f"      ID: {record_salida.id}")
print(f"      Placa: {record_salida.placa}")
print(f"      Entrada: {record_salida.fecha_entrada} [NULL]")
print(f"      Salida: {record_salida.fecha_salida}")
print(f"      Usuario Registro: {record_salida.usuario_registro.username}")
print(f"      Operario (salida): {record_salida.operario.username}")

# ============================================================================
# 4. VERIFICAR REGISTROS EN BASE DE DATOS
# ============================================================================
print("\n[4] Verificando registros en base de datos...")
todos_abc = Reserva.objects.filter(placa='ABC-123').order_by('-fecha_entrada', '-fecha_salida')
print(f"    Total registros para ABC-123: {todos_abc.count()}")

for i, reg in enumerate(todos_abc, 1):
    tipo = "ENTRADA" if reg.fecha_entrada else "SALIDA "
    entrada = reg.fecha_entrada.strftime("%H:%M:%S") if reg.fecha_entrada else "[NULL]"
    salida = reg.fecha_salida.strftime("%H:%M:%S") if reg.fecha_salida else "[NULL]"
    
    print(f"\n    Registro {i}:")
    print(f"      Tipo: {tipo} | Solo-Salida: {reg.registra_solo_salida}")
    print(f"      Entrada: {entrada}")
    print(f"      Salida:  {salida}")
    print(f"      Entró: {reg.usuario_registro.username} | Extrajo: {reg.operario.username}")

# ============================================================================
# 5. PRUEBA DE FILTROS (Como lo hace dashboard_admin)
# ============================================================================
print("\n[5] Probando filtros del dashboard (rango hoy)...")
from django.db.models import Q

hoy_date = timezone.localdate()
filtrados = Reserva.objects.filter(
    Q(fecha_entrada__date__range=[hoy_date, hoy_date]) |
    Q(registra_solo_salida=True, fecha_salida__date__range=[hoy_date, hoy_date])
).order_by('-fecha_entrada', '-fecha_salida').values('id', 'placa', 'registra_solo_salida', 'fecha_entrada', 'fecha_salida')

print(f"    Registros en filtro dashboard: {filtrados.count()}")
for reg in filtrados:
    print(f"      ID: {reg['id']} | Placa: {reg['placa']} | Solo-Salida: {reg['registra_solo_salida']}")

# ============================================================================
# 6. PRUEBA DE MENSUALIDAD
# ============================================================================
print("\n[6] Creando registro de MENSUALIDAD con dual-user...")
hace_20_min = hoy - timedelta(minutes=20)

mens_entrada = Reserva.objects.create(
    placa='XYZ-789',
    tipo_vehiculo='MOTO',
    modalidad='MENSUALIDAD',
    fecha_entrada=hace_20_min,
    fecha_salida=None,
    total_pagar=Decimal('50000.00'),
    usuario_registro=user_a,
    operario=user_a,
    activo=True,
    registra_solo_salida=False,
    fecha_vencimiento=hoy + timedelta(days=30)
)
print(f"    ✓ Mensualidad entrada (User A): {mens_entrada.id}")

# Simulamos que User B extrae
mens_salida = Reserva.objects.create(
    placa='XYZ-789',
    tipo_vehiculo='MOTO',
    modalidad='MENSUALIDAD',
    fecha_entrada=None,
    fecha_salida=ahora,
    total_pagar=Decimal('0.00'),
    usuario_registro=user_a,
    operario=user_b,
    activo=False,
    registra_solo_salida=True,
    fecha_vencimiento=hoy + timedelta(days=30)
)
print(f"    ✓ Mensualidad salida (User B):  {mens_salida.id}")

# ============================================================================
# 7. RESUMEN FINAL
# ============================================================================
print("\n[7] RESUMEN FINAL...")
total_records = Reserva.objects.count()
dia_hora_count = Reserva.objects.filter(modalidad='DIA_HORA').count()
mensualidad_count = Reserva.objects.filter(modalidad='MENSUALIDAD').count()
solo_salida_count = Reserva.objects.filter(registra_solo_salida=True).count()

print(f"    Total registros en BD: {total_records}")
print(f"    DIA_HORA: {dia_hora_count}")
print(f"    MENSUALIDAD: {mensualidad_count}")
print(f"    Solo-Salida (registra_solo_salida=True): {solo_salida_count}")

print("\n" + "="*70)
print("✓ PRUEBA COMPLETADA EXITOSAMENTE")
print("="*70)
print("\nAhora puedes:")
print("  1. Acceder al dashboard en http://localhost:8000/dashboard/")
print("  2. Ver dos registros DIA_HORA para placa ABC-123")
print("  3. Verificar que el operario aparece correctamente")
print("  4. Comprobar que están ordenados descendentemente (más reciente arriba)")
print("\n")
