from django.contrib import admin
from django.utils import timezone

from .models import Reserva


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'placa',
        'tipo_vehiculo',
        'modalidad',
        'fecha_entrada',
        'fecha_salida',
        'fecha_vencimiento',
        'total_pagar',
        'activo',
        'usuario_registro',
        'operario',
    )
    list_filter = (
        'modalidad',
        'tipo_vehiculo',
        'activo',
        'fecha_entrada',
        'fecha_salida',
        'fecha_vencimiento',
    )
    search_fields = (
        'placa',
        'usuario_registro__username',
        'operario__username',
    )
    ordering = ('-fecha_entrada',)
    list_per_page = 25
    date_hierarchy = 'fecha_entrada'
    list_editable = ('activo', 'total_pagar')
    readonly_fields = ('fecha_entrada',)
    actions = ('marcar_como_salida', 'marcar_como_activo')

    fieldsets = (
        ('Datos del vehiculo', {
            'fields': ('placa', 'tipo_vehiculo', 'modalidad', 'activo'),
        }),
        ('Cobro y vigencia', {
            'fields': ('total_pagar', 'fecha_vencimiento'),
        }),
        ('Fechas del movimiento', {
            'fields': ('fecha_entrada', 'fecha_salida'),
        }),
        ('Usuarios', {
            'fields': ('usuario_registro', 'operario'),
        }),
    )

    @admin.action(description='Marcar seleccionados como salida')
    def marcar_como_salida(self, request, queryset):
        queryset.update(activo=False, fecha_salida=timezone.now(), operario=request.user)

    @admin.action(description='Marcar seleccionados como activos')
    def marcar_como_activo(self, request, queryset):
        queryset.update(activo=True, fecha_salida=None, operario=request.user)