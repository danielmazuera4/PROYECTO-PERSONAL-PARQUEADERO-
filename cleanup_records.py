#!/usr/bin/env python
"""
Script para eliminar TODOS los registros de placas (Reserva)
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'daniel_parqueadero.settings')
django.setup()

from reservas.models import Reserva

print("\n" + "="*70)
print("LIMPIAR BASE DE DATOS - ELIMINAR TODOS LOS REGISTROS")
print("="*70)

# Obtener cantidad actual
total_antes = Reserva.objects.count()
print(f"\n📊 Registros actuales: {total_antes}")

if total_antes > 0:
    # Eliminar todos
    Reserva.objects.all().delete()
    total_despues = Reserva.objects.count()
    print(f"🗑️  Eliminados: {total_antes} registros")
    print(f"✓ Registros restantes: {total_despues}")
else:
    print("✓ La base de datos ya está vacía")

print("\n" + "="*70)
print("✓ LIMPIEZA COMPLETADA")
print("="*70 + "\n")
